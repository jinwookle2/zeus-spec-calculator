"""교환 재배송분 공급사 재발주: 자동 재발주 → 송장 수집 → 네이버 교환 재배송, 승인/수동/재시도 경로."""
from decimal import Decimal

from app.models import DeadLetter, ExchangeReorder, Order, OrderStatus, PurchaseOrder, Supplier
from tests.test_operations import _delivered_order, _run


def _exchange_requested(client, h, db):
    poid, order = _delivered_order(client, h, db)
    client.post(f"/api/mock/orders/{poid}/status", json={"status": "DELIVERED", "claim_type": "EXCHANGE"}, headers=h)
    _run(client, h, "collect_orders")
    db.expire_all()
    order = db.get(Order, order.id)
    assert order.status == OrderStatus.EXCHANGE_REQUESTED
    return order


def test_exchange_auto_reorder_and_redispatch(client, op_h, db):
    order = _exchange_requested(client, op_h, db)
    assert db.query(ExchangeReorder).count() == 0  # 수거 완료 전에는 재발주하지 않음
    assert client.post(f"/api/orders/{order.id}/exchange/collect-approve", headers=op_h).status_code == 200
    db.expire_all()
    ex = db.query(ExchangeReorder).filter_by(order_id=order.id).one()
    po = db.query(PurchaseOrder).filter_by(order_id=order.id).one()
    assert ex.status.value == "CONFIRMED" and ex.supplier_order_no.startswith("MOCK-")
    assert ex.supplier_order_no != po.supplier_order_no  # 별도 멱등키 → 원 발주와 다른 발주번호
    assert ex.amount == po.amount and not ex.dry_run

    # 수거 완료를 다시 눌러도 재발주는 1건
    client.post(f"/api/orders/{order.id}/exchange/collect-approve", headers=op_h)
    assert db.query(ExchangeReorder).count() == 1

    res = _run(client, op_h, "poll_shipments")
    assert res["exchange_redispatched"] == 1
    db.expire_all()
    order, ex = db.get(Order, order.id), db.get(ExchangeReorder, ex.id)
    assert order.status == OrderStatus.TRACKING_REGISTERED and order.claim_status == "EXCHANGE_REDISPATCHED"
    assert ex.status.value == "SHIPPED" and ex.tracking_no
    logs = client.get("/api/api-logs", headers=op_h).json()
    sent = next(l for l in logs if l["action"] == "exchange_dispatch")
    assert sent["request"]["reDeliveryTrackingNumber"] == ex.tracking_no
    # 다음 폴링에서 중복 처리 없음
    assert _run(client, op_h, "poll_shipments")["exchange_redispatched"] == 0

    detail = client.get(f"/api/orders/{order.id}", headers=op_h).json()
    assert detail["exchange_reorder"]["supplier_order_no"] == ex.supplier_order_no
    rev = client.get("/api/analytics/revenue", headers=op_h).json()
    assert Decimal(rev["exchange_reorder_cost"]) == ex.amount
    assert Decimal(rev["supplier_cost"]) == po.amount + ex.amount


def test_exchange_reorder_requires_approval_when_auto_disabled(client, op_h, admin_h, db):
    client.put("/api/settings", json={"auto_exchange_reorder_enabled": False}, headers=admin_h)
    order = _exchange_requested(client, op_h, db)
    client.post(f"/api/orders/{order.id}/exchange/collect-approve", headers=op_h)
    db.expire_all()
    ex = db.query(ExchangeReorder).filter_by(order_id=order.id).one()
    assert ex.status.value == "PENDING_APPROVAL" and ex.supplier_order_no is None
    assert any("교환 재발주 승인 필요" in a["message"] for a in client.get("/api/alerts", headers=op_h).json())
    assert _run(client, op_h, "poll_shipments")["exchange_redispatched"] == 0

    listed = client.get("/api/exchange-reorders?status=PENDING_APPROVAL", headers=op_h).json()
    assert [x["id"] for x in listed] == [ex.id]
    r = client.post(f"/api/exchange-reorders/{ex.id}/approve", json={"supplier_order_no": "MANUAL-EX-1"}, headers=op_h)
    assert r.status_code == 200, r.text
    assert r.json()["result"] == "CONFIRMED"
    assert client.post(f"/api/exchange-reorders/{ex.id}/approve", json={}, headers=op_h).status_code == 409
    assert _run(client, op_h, "poll_shipments")["exchange_redispatched"] == 1


def test_manual_redispatch_cancels_pending_reorder(client, op_h, admin_h, db):
    client.put("/api/settings", json={"auto_exchange_reorder_enabled": False}, headers=admin_h)
    order = _exchange_requested(client, op_h, db)
    client.post(f"/api/orders/{order.id}/exchange/collect-approve", headers=op_h)
    r = client.post(f"/api/orders/{order.id}/exchange/redispatch", json={"carrier_code": "CJ", "tracking_no": "987654321"},
                    headers=op_h)
    assert r.status_code == 200, r.text
    db.expire_all()
    ex = db.query(ExchangeReorder).filter_by(order_id=order.id).one()
    assert ex.status.value == "CANCELLED"  # 다른 경로로 재배송 → 남은 재발주는 취소 (중복 발주 방지)
    assert client.post(f"/api/exchange-reorders/{ex.id}/approve", json={}, headers=op_h).status_code == 409


def test_exchange_reorder_retry_then_dead_letter(client, op_h, db):
    order = _exchange_requested(client, op_h, db)
    sup = db.query(Supplier).filter_by(code="MOCKA").one()
    sup.config = {**sup.config, "fail_purchase_times": 10}
    db.commit()
    client.post(f"/api/orders/{order.id}/exchange/collect-approve", headers=op_h)
    res1, res2 = _run(client, op_h, "retry_purchases"), _run(client, op_h, "retry_purchases")
    assert res1["exchange_retried"] == 1 and res2["exchange_retried"] == 1
    db.expire_all()
    ex = db.query(ExchangeReorder).filter_by(order_id=order.id).one()
    assert ex.status.value == "FAILED" and ex.attempts == 3
    assert db.get(Order, order.id).status == OrderStatus.EXCHANGE_REQUESTED  # 주문 자체는 실패 처리하지 않음
    assert db.query(DeadLetter).filter_by(task_name="submit_exchange_reorder").count() == 1
    # 공급사 복구 후 관리자 재승인
    sup = db.query(Supplier).filter_by(code="MOCKA").one()
    sup.config = {**sup.config, "fail_purchase_times": 0}
    db.commit()
    r = client.post(f"/api/exchange-reorders/{ex.id}/approve", json={}, headers=op_h)
    assert r.status_code == 200 and r.json()["result"] == "CONFIRMED"
