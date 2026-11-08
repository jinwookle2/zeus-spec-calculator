"""LIVE 모드라도 안전 스위치가 꺼져 있으면 실제 등록/발주/개인정보 전송이 일어나지 않는지 검증."""
import bcrypt
import httpx

from app.adapters.base import PurchaseRequest, PurchaseResult, StockInfo, SupplierAdapter
from app.adapters import registry
from app.config import Settings
from app.models import Product, ProductStatus
from app.naver.client import LiveNaverClient
from app.services import fulfillment, listing, mock_sim, sourcing


def _live(db, **flags):
    secret = bcrypt.gensalt(rounds=4).decode()
    calls = []

    def handler(req):
        calls.append(f"{req.method} {req.url.path}")
        if req.url.path.endswith("/oauth2/token"):
            return httpx.Response(200, json={"access_token": "AT", "expires_in": 10800})
        if req.url.path.endswith("/v2/tags/restricted-tags"):
            tags = req.url.params.get_list("tags")
            return httpx.Response(200, json=[{"tag": t, "restricted": t == "텀블러"} for t in tags])
        return httpx.Response(200, json={"originProductNo": 1})

    http = httpx.Client(base_url="https://api.commerce.naver.com/external", transport=httpx.MockTransport(handler))
    s = Settings(naver_mode="live", naver_client_id="cid", naver_client_secret=secret, naver_rps=1000, **flags)
    return LiveNaverClient(db, s, http=http), calls


def test_publish_in_live_mode_without_gate_is_dry_run(db):
    from app.models import Supplier
    from app.services.settings_service import update_settings

    update_settings(db, {"origin_area_codes": {"중국": "0200037"}}, "test")
    sourcing.sync_supplier(db, db.query(Supplier).filter_by(code="MOCKA").one())
    listing.process_new_candidates(db)
    nv, calls = _live(db)
    res = listing.publish_approved(db, nv)
    assert res["listed"] > 0
    assert not any("/v2/products" in c for c in calls)   # 실제 등록 호출 없음
    p = db.query(Product).filter_by(status=ProductStatus.LISTED).first()
    assert p.dry_run_listed and p.naver_origin_product_no.startswith("DRYRUN-")
    # 제한 태그 조회(읽기)는 실제 호출되고, 제한 태그는 등록 전에 제거된다
    assert any("/v2/tags/restricted-tags" in c for c in calls)
    t = db.query(Product).filter_by(listing_key="MOCKA:MA-1001").one()
    assert "텀블러" not in t.tags and any("RESTRICTED_TAGS_REMOVED" in w for w in t.warnings)


def test_live_mode_requires_origin_code_mapping(db):
    from app.models import Supplier

    sourcing.sync_supplier(db, db.query(Supplier).filter_by(code="MOCKA").one())
    listing.process_new_candidates(db)
    nv, _ = _live(db)
    res = listing.publish_approved(db, nv)
    assert res["listed"] == 0 and res["failed"] > 0
    assert "원산지 코드" in db.query(Product).filter_by(status=ProductStatus.FAILED).first().last_error


class LiveFake(SupplierAdapter):
    is_live = True
    supports_purchase = True
    placed: list = []

    def fetch_products(self):
        from app.adapters.mock_supplier import MockSupplierAdapter

        return MockSupplierAdapter(self.code, {"prefix": "MA"}).fetch_products()

    def get_stock(self, sku):
        from decimal import Decimal

        return StockInfo(sku, 100, Decimal("6900"), True)

    def place_order(self, req: PurchaseRequest):
        LiveFake.placed.append(req)
        return PurchaseResult("REAL-1", "CONFIRMED")


def test_real_purchase_and_pii_gates(db, monkeypatch):
    from app.models import Order, Supplier

    monkeypatch.setitem(registry.ADAPTERS, "livefake", LiveFake)
    sup = db.query(Supplier).filter_by(code="MOCKA").one()
    sourcing.sync_supplier(db, sup)
    listing.process_new_candidates(db)
    from app.naver.client import MockNaverClient

    nv = MockNaverClient(db)
    listing.publish_approved(db, nv)
    p = db.query(Product).filter_by(listing_key="MOCKA:MA-1001").one()
    sup.adapter_type = "livefake"
    sup.pii_transfer_agreed = True
    db.flush()
    mock_sim.simulate_order(db, p, 1, seed=1)
    fulfillment.collect_orders(db, nv)

    # 1) ALLOW_REAL_PURCHASE=false → 공급사 호출 없음, 승인 대기
    LiveFake.placed = []
    fulfillment.process_paid_orders(db, nv)
    order = db.query(Order).one()
    assert LiveFake.placed == [] and order.status.value == "AWAITING_APPROVAL"

    # 2) 실제 발주 허용, PII 전송 불허 → 마스킹된 수령인 정보만 전달
    import app.services.fulfillment as f

    monkeypatch.setattr(f, "get_settings", lambda: Settings(allow_real_purchase=True, allow_pii_transfer=False))
    po = db.query(f.PurchaseOrder).one()
    f.approve_purchase(db, nv, po, "admin@example.com")
    assert len(LiveFake.placed) == 1 and LiveFake.placed[0].recipient["masked"] is True
    assert "****" in LiveFake.placed[0].recipient["phone"]
    assert po.supplier_order_no == "REAL-1"


def test_daily_purchase_amount_limit(db, monkeypatch):
    from app.models import Order, Supplier
    from app.services.settings_service import update_settings
    import app.services.fulfillment as f

    monkeypatch.setitem(registry.ADAPTERS, "livefake", LiveFake)
    monkeypatch.setattr(f, "get_settings", lambda: Settings(allow_real_purchase=True))
    update_settings(db, {"daily_purchase_amount_limit": 5000}, "test")
    sup = db.query(Supplier).filter_by(code="MOCKA").one()
    sourcing.sync_supplier(db, sup)
    listing.process_new_candidates(db)
    from app.naver.client import MockNaverClient

    nv = MockNaverClient(db)
    listing.publish_approved(db, nv)
    p = db.query(Product).filter_by(listing_key="MOCKA:MA-1001").one()
    sup.adapter_type = "livefake"
    db.flush()
    mock_sim.simulate_order(db, p, 1)
    fulfillment.collect_orders(db, nv)
    LiveFake.placed = []
    fulfillment.process_paid_orders(db, nv)
    assert LiveFake.placed == []
    o = db.query(Order).one()
    assert o.status.value == "ON_HOLD" and "한도" in o.hold_reason
