"""교환 처리, 정산 대사, 카테고리 동기화, 관리자 보안."""
from decimal import Decimal

from app.models import NaverCategory, Order, OrderStatus, Product, Settlement
from app.naver.client import MockNaverClient


def _run(client, h, job):
    r = client.post(f"/api/jobs/{job}/run", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _delivered_order(client, h, db, qty=1):
    for j in ("source_products", "process_candidates", "publish_listings"):
        _run(client, h, j)
    db.expire_all()
    p = db.query(Product).filter_by(listing_key="MOCKA:MA-1001").one()
    poid = client.post("/api/mock/orders", json={"product_id": p.id, "quantity": qty}, headers=h).json()["product_order_id"]
    for j in ("collect_orders", "process_orders", "poll_shipments"):
        _run(client, h, j)
    client.post(f"/api/mock/orders/{poid}/status", json={"status": "DELIVERED"}, headers=h)
    _run(client, h, "collect_orders")
    db.expire_all()
    return poid, db.query(Order).filter_by(naver_product_order_id=poid).one()


def test_exchange_collect_and_redispatch(client, op_h, db):
    poid, order = _delivered_order(client, op_h, db)
    assert order.status == OrderStatus.DELIVERED
    client.post(f"/api/mock/orders/{poid}/status", json={"status": "DELIVERED", "claim_type": "EXCHANGE"}, headers=op_h)
    _run(client, op_h, "collect_orders")
    db.expire_all()
    order = db.get(Order, order.id)
    assert order.status == OrderStatus.EXCHANGE_REQUESTED
    # 수거 완료 전 재배송 불가
    r = client.post(f"/api/orders/{order.id}/exchange/redispatch", json={"carrier_code": "롯데택배", "tracking_no": "123456789"}, headers=op_h)
    assert r.status_code == 409
    assert client.post(f"/api/orders/{order.id}/exchange/collect-approve", headers=op_h).status_code == 200
    r = client.post(f"/api/orders/{order.id}/exchange/redispatch", json={"carrier_code": "롯데택배", "tracking_no": "123456789"}, headers=op_h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "TRACKING_REGISTERED" and r.json()["claim_status"] == "EXCHANGE_REDISPATCHED"
    logs = client.get("/api/api-logs", headers=op_h).json()
    sent = next(l for l in logs if l["action"] == "exchange_dispatch")
    assert sent["request"]["reDeliveryCompany"] == "HYUNDAI"  # 롯데택배 공식 코드


def test_settlement_reconcile_matches_and_flags_fee_mismatch(client, op_h, admin_h, db):
    _, order = _delivered_order(client, op_h, db, qty=2)
    res = _run(client, op_h, "reconcile_settlements")
    assert res["fetched"] == 1 and res["matched"] == 1 and res["mismatch"] == 0  # 기본 수수료율 = Mock 실제 수수료
    st = db.query(Settlement).one()
    assert st.order_id == order.id and st.commission_amount == (order.total_amount * Decimal("0.0363")).quantize(Decimal("1")) + (order.total_amount * Decimal("0.02")).quantize(Decimal("1"))
    rev = client.get("/api/analytics/revenue", headers=op_h).json()
    assert rev["settled_orders"] == 1 and Decimal(rev["platform_fees"]) == st.commission_amount
    # 설정 수수료율이 실제와 다르면 불일치 알림
    client.put("/api/settings", json={"platform_fee_rates": {"fee": 0.03}}, headers=admin_h)
    res = _run(client, op_h, "reconcile_settlements")
    assert res["mismatch"] == 1 and res["new_mismatch"] == 1
    assert any(a["category"] == "settlement" for a in client.get("/api/alerts", headers=op_h).json())
    assert len(client.get("/api/settlements?mismatch_only=true", headers=op_h).json()) == 1
    # 재실행해도 중복 생성/중복 알림 없음
    res = _run(client, op_h, "reconcile_settlements")
    assert res["created"] == 0 and res["new_mismatch"] == 0


def test_category_sync_used_for_recommendation(client, op_h, db, monkeypatch):
    cats = [{"id": "50009999", "name": "텀블러", "wholeCategoryName": "생활/건강>주방용품>텀블러", "last": True},
            {"id": "50000000", "name": "주방용품", "wholeCategoryName": "생활/건강>주방용품", "last": False}]
    monkeypatch.setattr(MockNaverClient, "get_categories", lambda self: cats)
    assert _run(client, op_h, "sync_categories")["created"] == 2
    assert db.query(NaverCategory).count() == 2
    _run(client, op_h, "source_products")
    _run(client, op_h, "process_candidates")
    p = db.query(Product).filter_by(listing_key="MOCKA:MA-1001").one()
    assert p.category_id == "50009999"  # 동기화된 리프 카테고리 사용
    found = client.get("/api/categories?q=텀블러", headers=op_h).json()
    assert found["total"] == 1 and found["items"][0]["id"] == "50009999"
    conn = client.get("/api/connections", headers=op_h).json()
    assert conn["categories"]["synced_count"] == 2


def test_restricted_tags_removed_before_listing(client, op_h, db):
    for j in ("source_products", "process_candidates"):
        _run(client, op_h, j)
    p = db.query(Product).filter_by(listing_key="MOCKA:MA-1001").one()
    p.tags = list(p.tags) + ["최저가", "무료배송"]
    db.commit()
    _run(client, op_h, "publish_listings")
    db.expire_all()
    p = db.get(Product, p.id)
    assert "최저가" not in p.tags and "무료배송" not in p.tags
    assert any("RESTRICTED_TAGS_REMOVED" in w for w in p.warnings)


def test_login_lockout_and_password_change(client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "op@example.com", "password": "wrong"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "op@example.com", "password": "operator123"})
    assert r.status_code == 429  # 올바른 비밀번호도 잠금 중에는 거부

    r = client.post("/api/auth/login", json={"email": "viewer@example.com", "password": "viewer1234"})
    assert r.json()["password_change_recommended"] is True
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.post("/api/auth/password", json={"current_password": "x", "new_password": "newpassword123"}, headers=h).status_code == 400
    assert client.post("/api/auth/password", json={"current_password": "viewer1234", "new_password": "short"}, headers=h).status_code == 422
    assert client.post("/api/auth/password", json={"current_password": "viewer1234", "new_password": "newpassword123"}, headers=h).status_code == 200
    assert client.post("/api/auth/login", json={"email": "viewer@example.com", "password": "viewer1234"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": "viewer@example.com", "password": "newpassword123"})
    assert r.status_code == 200 and r.json()["password_change_recommended"] is False
