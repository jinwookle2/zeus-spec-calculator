"""Mock 데이터 기반 전체 워크플로 통합 테스트 (API 경유)."""
from app.models import (
    DeadLetter, Order, OrderEvent, OrderStatus, Product, ProductStatus, PurchaseOrder, Supplier, SupplierProduct,
    SupplierProductStatus,
)


def _sup(db, code):
    return db.query(Supplier).filter_by(code=code).one()


def _admin(client):
    r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin1234!"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _run(client, h, job):
    r = client.post(f"/api/jobs/{job}/run", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_sourcing_detects_duplicates_soldout_discontinued(client, op_h, db):
    _run(client, op_h, "source_products")
    sp = {x.supplier_sku: x for x in db.query(SupplierProduct).join(Supplier).filter(Supplier.code == "MOCKA")}
    assert sp["MA-2005"].status == SupplierProductStatus.DUPLICATE and sp["MA-2005"].duplicate_of_id == sp["MA-1001"].id
    assert sp["MA-2003"].status == SupplierProductStatus.SOLD_OUT
    assert sp["MA-2007"].status == SupplierProductStatus.DISCONTINUED
    # 공급사 간 동일 상품도 중복으로 감지 (나중에 수집된 쪽이 DUPLICATE)
    r = client.post("/api/suppliers", json={"code": "MOCKC", "name": "C", "config": {"prefix": "MC"}},
                    headers=_admin(client))
    assert r.status_code == 200
    _run(client, op_h, "source_products")
    c = db.query(SupplierProduct).filter_by(supplier_sku="MC-1001").one()
    assert c.status == SupplierProductStatus.DUPLICATE and c.duplicate_of_id == sp["MA-1001"].id
    # 재실행해도 중복 생성 없음 (공급사코드+상품코드 유니크)
    before = db.query(SupplierProduct).count()
    _run(client, op_h, "source_products")
    assert db.query(SupplierProduct).count() == before


def test_processing_blocks_and_auto_approval(client, op_h, db):
    _run(client, op_h, "source_products")
    _run(client, op_h, "process_candidates")
    prods = {p.listing_key: p for p in db.query(Product)}
    # 검증된 공급사 A: 정상 상품은 자동 승인
    assert prods["MOCKA:MA-1001"].status == ProductStatus.APPROVED
    assert prods["MOCKA:MA-1001"].margin_rate >= 0.25
    # 차단 사례
    assert any(b.startswith("BRAND_NOT_AUTHORIZED") for b in prods["MOCKA:MA-2001"].block_reasons)
    assert any(b.startswith("BANNED_KEYWORD") for b in prods["MOCKA:MA-2002"].block_reasons)
    assert any(b.startswith("PRICE_ABOVE_MARKET") for b in prods["MOCKA:MA-2004"].block_reasons)
    assert prods["MOCKA:MA-2006"].status == ProductStatus.BLOCKED
    # 중복/품절/단종은 가공 대상 아님
    assert "MOCKA:MA-2005" not in prods and "MOCKA:MA-2003" not in prods
    # 미검증 공급사 B: 승인 대기
    assert prods["MOCKB:MB-1001"].status == ProductStatus.PENDING_APPROVAL


def test_daily_listing_limit_and_no_duplicate_listing(client, op_h, admin_h, db):
    r = client.put("/api/settings", json={"daily_listing_limit": 3}, headers=admin_h)
    assert r.status_code == 200
    _run(client, op_h, "source_products")
    _run(client, op_h, "process_candidates")
    res = _run(client, op_h, "publish_listings")
    assert res["listed"] == 3 and res["skipped_limit"] > 0
    res2 = _run(client, op_h, "publish_listings")
    assert res2["listed"] == 0  # 오늘 한도 소진
    listed = db.query(Product).filter_by(status=ProductStatus.LISTED).all()
    assert len({p.naver_origin_product_no for p in listed}) == 3


def test_manual_approval_with_price_override(client, op_h, db):
    _run(client, op_h, "source_products")
    _run(client, op_h, "process_candidates")
    p = db.query(Product).filter_by(listing_key="MOCKB:MB-1001").one()
    # 최소 이익 미달 가격으로 승인 시도 → 차단
    r = client.post(f"/api/products/{p.id}/approve", json={"sale_price": 9000}, headers=op_h)
    assert r.status_code == 422 and "MARGIN_BELOW_TARGET" in r.text
    # 시장가(24,900) 초과 가격도 차단
    r = client.post(f"/api/products/{p.id}/approve", json={"sale_price": 25000}, headers=op_h)
    assert r.status_code == 422 and "PRICE_ABOVE_MARKET" in r.text
    r = client.post(f"/api/products/{p.id}/approve", json={"sale_price": 24000}, headers=op_h)
    assert r.status_code == 200 and r.json()["status"] == "APPROVED"


def test_listing_failure_is_recorded(client, op_h, db):
    from app.naver.client import MockNaverClient

    MockNaverClient.fail_listing_keys = {"MOCKA:MA-1002"}
    _run(client, op_h, "source_products")
    _run(client, op_h, "process_candidates")
    _run(client, op_h, "publish_listings")
    p = db.query(Product).filter_by(listing_key="MOCKA:MA-1002").one()
    assert p.status == ProductStatus.FAILED and "필수 고시정보" in p.last_error
    detail = client.get(f"/api/products/{p.id}", headers=op_h).json()
    assert any(not l["success"] for l in detail["api_logs"])


def _listed_product(client, op_h, db, key="MOCKA:MA-1001"):
    for j in ("source_products", "process_candidates", "publish_listings"):
        _run(client, op_h, j)
    db.expire_all()
    return db.query(Product).filter_by(listing_key=key).one()


def test_full_order_flow_auto_purchase_to_delivered(client, op_h, db):
    p = _listed_product(client, op_h, db)
    assert p.status == ProductStatus.LISTED
    po_id = client.post("/api/mock/orders", json={"product_id": p.id, "quantity": 2}, headers=op_h).json()["product_order_id"]

    assert _run(client, op_h, "collect_orders")["new"] == 1
    assert _run(client, op_h, "collect_orders")["new"] == 0  # 중복 수집 방지
    res = _run(client, op_h, "process_orders")
    assert res["auto_purchased"] == 1
    db.expire_all()
    order = db.query(Order).filter_by(naver_product_order_id=po_id).one()
    assert order.status == OrderStatus.SUPPLIER_CONFIRMED
    po = db.query(PurchaseOrder).filter_by(order_id=order.id).one()
    assert po.supplier_order_no.startswith("MOCK-") and po.amount == p.supplier_product.supply_price * 2 + 3000

    assert _run(client, op_h, "poll_shipments")["registered"] == 1
    db.expire_all()
    order = db.get(Order, order.id)
    po = db.get(PurchaseOrder, po.id)
    assert order.status == OrderStatus.TRACKING_REGISTERED and po.naver_carrier_code == "CJGLS"

    client.post(f"/api/mock/orders/{po_id}/status", json={"status": "DELIVERED"}, headers=op_h)
    _run(client, op_h, "collect_orders")
    db.expire_all()
    order = db.get(Order, order.id)
    assert order.status == OrderStatus.DELIVERED
    steps = [e.to_status for e in db.query(OrderEvent).filter_by(order_id=order.id).order_by(OrderEvent.id)]
    assert steps == ["PAID", "STOCK_CHECKED", "PURCHASE_REQUESTED", "SUPPLIER_CONFIRMED", "SHIPPED",
                     "TRACKING_REGISTERED", "DELIVERED"]
    # PII 는 암호화 저장 + 기본 마스킹
    assert "010-" not in (order.buyer_phone_enc or "")
    d = client.get(f"/api/orders/{order.id}", headers=op_h).json()
    assert "****" in d["buyer"]["phone"]
    assert client.get(f"/api/orders/{order.id}?reveal=true", headers=op_h).status_code == 403
    rev = revenue = client.get("/api/analytics/revenue", headers=op_h).json()
    assert rev["orders"] == 1 and float(revenue["estimated_profit"]) > 0


def test_unverified_supplier_requires_purchase_approval(client, op_h, db):
    _run(client, op_h, "source_products")
    _run(client, op_h, "process_candidates")
    p = db.query(Product).filter_by(listing_key="MOCKB:MB-1001").one()
    client.post(f"/api/products/{p.id}/approve", json={}, headers=op_h)
    _run(client, op_h, "publish_listings")
    client.post("/api/mock/orders", json={"product_id": p.id}, headers=op_h)
    _run(client, op_h, "collect_orders")
    assert _run(client, op_h, "process_orders")["awaiting_approval"] == 1
    po = db.query(PurchaseOrder).one()
    db.refresh(po)
    assert po.order.status == OrderStatus.AWAITING_APPROVAL and po.supplier_order_no is None
    r = client.post(f"/api/purchases/{po.id}/approve", json={}, headers=op_h)
    assert r.status_code == 200 and r.json()["result"] == "CONFIRMED"
    # 같은 발주 재승인 → 중복 발주 안 됨
    assert client.post(f"/api/purchases/{po.id}/approve", json={}, headers=op_h).status_code == 409


def test_stock_mismatch_holds_order_and_pauses_auto_purchase(client, op_h, db):
    p = _listed_product(client, op_h, db)
    client.post("/api/mock/orders", json={"product_id": p.id, "quantity": 5}, headers=op_h)
    sup = _sup(db, "MOCKA")
    sup.config = {**sup.config, "stock_overrides": {"MA-1001": 1}}
    db.commit()
    _run(client, op_h, "collect_orders")
    res = _run(client, op_h, "process_orders")
    assert res["on_hold"] == 1
    db.expire_all()
    assert db.query(Order).one().status == OrderStatus.ON_HOLD
    sup = _sup(db, "MOCKA")
    assert sup.auto_purchase_paused and "재고" in sup.pause_reason
    alerts = client.get("/api/alerts", headers=op_h).json()
    assert any(a["category"] == "inventory_mismatch" for a in alerts)


def test_purchase_retry_then_dead_letter(client, op_h, admin_h, db):
    p = _listed_product(client, op_h, db)
    sup = _sup(db, "MOCKA")
    sup.config = {**sup.config, "fail_purchase_times": 10}
    db.commit()
    client.post("/api/mock/orders", json={"product_id": p.id}, headers=op_h)
    _run(client, op_h, "collect_orders")
    assert _run(client, op_h, "process_orders")["failed"] == 1
    _run(client, op_h, "retry_purchases")
    _run(client, op_h, "retry_purchases")
    db.expire_all()
    po = db.query(PurchaseOrder).one()
    assert po.status.value == "FAILED" and po.attempts == 3
    assert po.order.status == OrderStatus.FAILED
    assert db.query(DeadLetter).count() == 1


def test_purchase_retry_succeeds(client, op_h, db):
    p = _listed_product(client, op_h, db)
    sup = _sup(db, "MOCKA")
    sup.config = {**sup.config, "fail_purchase_times": 1}
    db.commit()
    client.post("/api/mock/orders", json={"product_id": p.id}, headers=op_h)
    _run(client, op_h, "collect_orders")
    _run(client, op_h, "process_orders")
    _run(client, op_h, "retry_purchases")
    db.expire_all()
    po = db.query(PurchaseOrder).one()
    assert po.status.value == "CONFIRMED" and po.attempts == 2


def test_cancel_before_purchase(client, op_h, db):
    _run(client, op_h, "source_products")
    _run(client, op_h, "process_candidates")
    p = db.query(Product).filter_by(listing_key="MOCKB:MB-1001").one()
    client.post(f"/api/products/{p.id}/approve", json={}, headers=op_h)
    _run(client, op_h, "publish_listings")
    poid = client.post("/api/mock/orders", json={"product_id": p.id}, headers=op_h).json()["product_order_id"]
    _run(client, op_h, "collect_orders")
    _run(client, op_h, "process_orders")
    client.post(f"/api/mock/orders/{poid}/status", json={"status": "CANCELED", "claim_type": "CANCEL"}, headers=op_h)
    _run(client, op_h, "collect_orders")
    db.expire_all()
    assert db.query(Order).one().status == OrderStatus.CANCELLED
    assert db.query(PurchaseOrder).one().status.value == "CANCELLED"


def test_inventory_sync_soldout_and_restock(client, op_h, db):
    p = _listed_product(client, op_h, db)
    sup = _sup(db, "MOCKA")
    sup.config = {**sup.config, "stock_overrides": {"MA-1001": 0}}
    db.commit()
    assert _run(client, op_h, "sync_inventory")["sold_out"] >= 1
    db.expire_all()
    assert db.get(Product, p.id).status == ProductStatus.SOLD_OUT
    sup = _sup(db, "MOCKA")
    sup.config = {**sup.config, "stock_overrides": {"MA-1001": 7}}
    db.commit()
    assert _run(client, op_h, "sync_inventory")["restocked"] >= 1
    db.expire_all()
    p = db.get(Product, p.id)
    assert p.status == ProductStatus.LISTED and p.stock == 7


def test_rbac_and_settings_validation(client, viewer_h, op_h, admin_h):
    assert client.get("/api/dashboard", headers=viewer_h).status_code == 200
    assert client.post("/api/jobs/source_products/run", headers=viewer_h).status_code == 403
    assert client.put("/api/settings", json={"daily_listing_limit": 10}, headers=op_h).status_code == 403
    assert client.put("/api/settings", json={"target_margin_rate": 1.5}, headers=admin_h).status_code == 422
    assert client.put("/api/settings", json={"unknown": 1}, headers=admin_h).status_code == 422
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/audit-logs", headers=op_h).status_code == 403


def test_service_token_for_n8n(client):
    r = client.post("/api/jobs/source_products/run", headers={"X-Service-Token": "test-service-token"})
    assert r.status_code == 200
    assert client.post("/api/jobs/source_products/run", headers={"X-Service-Token": "wrong"}).status_code == 401


def test_pipeline_endpoint_and_dashboard(client, op_h):
    r = client.post("/api/jobs/pipeline/run", headers=op_h)
    assert r.status_code == 200 and set(r.json()) >= {"source_products", "publish_listings", "poll_shipments"}
    d = client.get("/api/dashboard", headers=op_h).json()
    assert d["products"].get("LISTED", 0) > 0 and d["daily_listing_limit"] == 30
