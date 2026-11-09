"""주문 수집 → 재고 재확인 → 공급사 발주 → 송장 수집 → 네이버 발송처리 → 배송완료, 클레임 처리."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.adapters.base import AdapterError, PurchaseNotSupported, PurchaseRequest
from app.adapters.registry import get_adapter
from app.config import get_settings
from app.logging_setup import log
from app.models import (
    AppSetting,
    Order,
    OrderEvent,
    OrderStatus as S,
    Product,
    PurchaseOrder,
    PurchaseStatus as P,
    Supplier,
    utcnow,
)
from app.naver.carriers import map_carrier
from app.naver.client import NaverApiError, NaverClient
from app.security import decrypt_pii, encrypt_pii, mask_address, mask_name, mask_phone
from app.services.alerts import audit, dead_letter, raise_alert
from app.services.order_state import transition
from app.services.settings_service import get_all_settings

SYSTEM = "system"
LAST_POLL_KEY = "_last_order_poll"


# --------------------------------------------------------------------- 주문 수집


def _parse(detail: dict) -> dict:
    """네이버 상품주문 상세 → 내부 필드 (공식 문서 v2.91.0 '상품 주문 정보 구조체' 기준).
    productId = 채널상품번호, originalProductId = 원상품번호, sellerProductCode = 판매자 상품코드."""
    po = detail.get("productOrder", {})
    od = detail.get("order", {})
    addr = po.get("shippingAddress", {}) or {}
    return {
        "product_order_id": str(po.get("productOrderId")),
        "order_id": str(od.get("orderId") or po.get("orderId") or ""),
        "status": po.get("productOrderStatus"),
        "claim_type": po.get("claimType"),
        "seller_code": po.get("sellerProductCode"),
        "origin_product_no": str(po.get("originalProductId") or ""),
        "channel_product_no": str(po.get("productId") or ""),
        "option_code": po.get("optionManageCode"),
        "option_text": po.get("productOption"),
        "quantity": int(po.get("quantity") or 1),
        "unit_price": Decimal(str(po.get("unitPrice") or 0)),
        "total": Decimal(str(po.get("totalPaymentAmount") or 0)),
        "name": addr.get("name"),
        "phone": addr.get("tel1"),
        "address": " ".join(filter(None, [addr.get("zipCode"), addr.get("baseAddress"), addr.get("detailedAddress")])),
        "paid_at": od.get("paymentDate"),
    }


def collect_orders(db: Session, naver: NaverClient) -> dict:
    row = db.get(AppSetting, LAST_POLL_KEY)
    since = (datetime.fromisoformat(row.value) if row else utcnow() - timedelta(hours=24)) - timedelta(minutes=5)
    started = utcnow()
    ids = naver.fetch_changed_order_ids(since)
    details = naver.get_product_orders(ids) if ids else []
    summary = {"changed": len(ids), "new": 0, "updated": 0, "unmatched": 0}
    for d in details:
        f = _parse(d)
        order = db.query(Order).filter_by(naver_product_order_id=f["product_order_id"]).one_or_none()
        if order is None:
            if f["status"] not in ("PAYED",):
                continue
            product = None
            if f["seller_code"]:
                product = db.query(Product).filter_by(listing_key=f["seller_code"]).one_or_none()
            if product is None and f["origin_product_no"]:
                product = db.query(Product).filter_by(naver_origin_product_no=f["origin_product_no"]).one_or_none()
            if product is None and f["channel_product_no"]:
                product = db.query(Product).filter_by(naver_channel_product_no=f["channel_product_no"]).one_or_none()
            order = Order(
                naver_product_order_id=f["product_order_id"], naver_order_id=f["order_id"],
                product_id=product.id if product else None, supplier_id=product.supplier_id if product else None,
                quantity=f["quantity"], option_text=f["option_text"], unit_price=f["unit_price"], total_amount=f["total"],
                buyer_name_enc=encrypt_pii(f["name"]), buyer_phone_enc=encrypt_pii(f["phone"]),
                address_enc=encrypt_pii(f["address"]), status=S.PAID,
                paid_at=datetime.fromisoformat(f["paid_at"]) if f["paid_at"] else utcnow(),
            )
            db.add(order)
            db.flush()
            db.add(OrderEvent(order_id=order.id, from_status=None, to_status=S.PAID.value, actor=SYSTEM, reason="주문 수집"))
            summary["new"] += 1
            if product is None:
                summary["unmatched"] += 1
                transition(db, order, S.ON_HOLD, SYSTEM, "매핑된 상품 없음 (sellerProductCode/originalProductId/productId)")
                raise_alert(db, "warning", "order", f"상품 매핑 실패 주문 {order.naver_product_order_id}")
            continue
        summary["updated"] += 1
        _apply_naver_status(db, naver, order, f)
    if row is None:
        db.add(AppSetting(key=LAST_POLL_KEY, value=started.isoformat(), updated_by=SYSTEM))
    else:
        row.value = started.isoformat()
    db.flush()
    return summary


def _apply_naver_status(db: Session, naver: NaverClient, order: Order, f: dict) -> None:
    st, claim = f["status"], f["claim_type"]
    if st in ("DELIVERED", "PURCHASE_DECIDED") and order.status == S.TRACKING_REGISTERED:
        transition(db, order, S.DELIVERED, "naver", f"네이버 상태 {st}")
        order.delivered_at = utcnow()
    elif claim == "CANCEL" or st == "CANCELED":
        handle_cancel(db, naver, order, actor="naver")
    elif claim == "RETURN" and order.status in (S.SHIPPED, S.TRACKING_REGISTERED, S.DELIVERED):
        order.claim_type = "RETURN"
        transition(db, order, S.RETURN_REQUESTED, "naver", "고객 반품 요청")
        request_supplier_return(db, order, "naver")
    elif claim == "EXCHANGE" and order.status in (S.TRACKING_REGISTERED, S.DELIVERED):
        order.claim_type = "EXCHANGE"
        transition(db, order, S.EXCHANGE_REQUESTED, "naver", "고객 교환 요청")
        raise_alert(db, "warning", "claim", f"교환 요청 {order.naver_product_order_id}: 수동 처리 필요")


# --------------------------------------------------------------------- 재고 확인 + 발주


def check_stock(db: Session, order: Order, s: dict) -> bool:
    product = order.product
    supplier = order.supplier
    adapter = get_adapter(supplier)
    sku = product.supplier_product.supplier_sku
    info = adapter.get_stock(sku)
    opt_ok = True
    if order.option_text and product.options_normalized:
        # 옵션 단위 재고는 공급사 상품 데이터 기준 (Adapter 가 옵션 재고 API 를 제공하면 교체)
        for o in product.supplier_product.options:
            if o.get("name") and order.option_text and o["name"].split(":")[-1] in order.option_text:
                opt_ok = (o.get("stock") or 0) >= order.quantity
    tol = Decimal(str(s["max_supply_price_increase_rate"]))
    base_price = product.supplier_product.supply_price
    reasons = []
    if not info.available or info.stock < order.quantity or not opt_ok:
        reasons.append(f"재고 부족: 공급사 {info.stock}개 < 주문 {order.quantity}개")
    if base_price > 0 and info.supply_price > base_price * (1 + tol):
        reasons.append(f"공급가 상승: {base_price} → {info.supply_price}")
    if reasons:
        reason = "; ".join(reasons)
        transition(db, order, S.ON_HOLD, SYSTEM, reason)
        if not supplier.auto_purchase_paused:
            supplier.auto_purchase_paused, supplier.pause_reason = True, f"재고/가격 불일치 ({order.naver_product_order_id}): {reason}"
            raise_alert(db, "error", "inventory_mismatch",
                        f"{supplier.code} 자동 발주 중단: {reason}", {"order": order.naver_product_order_id})
        return False
    transition(db, order, S.STOCK_CHECKED, SYSTEM, f"공급사 재고 {info.stock}")
    return True


def purchased_amount_today(db: Session) -> Decimal:
    start = datetime.combine(utcnow().date(), time.min, tzinfo=timezone.utc)
    total = (db.query(func.coalesce(func.sum(PurchaseOrder.amount), 0))
             .filter(PurchaseOrder.created_at >= start, PurchaseOrder.dry_run.is_(False),
                     PurchaseOrder.status.in_([P.REQUESTING, P.REQUESTED, P.CONFIRMED, P.SHIPPED])).scalar())
    return Decimal(str(total or 0))


def get_or_create_purchase(db: Session, order: Order) -> PurchaseOrder:
    po = db.query(PurchaseOrder).filter_by(order_id=order.id).one_or_none()
    if po:
        return po
    sp = order.product.supplier_product
    amount = sp.supply_price * order.quantity + sp.shipping_fee
    po = PurchaseOrder(order_id=order.id, idempotency_key=f"PO-{order.naver_product_order_id}",
                       supplier_id=order.supplier_id, amount=amount, status=P.PENDING_APPROVAL)
    db.add(po)
    db.flush()
    return po


def auto_purchase_allowed(supplier: Supplier, s: dict) -> tuple[bool, str]:
    adapter = get_adapter(supplier)
    if not s["auto_purchase_enabled"]:
        return False, "자동 발주 전역 비활성"
    if not adapter.supports_purchase:
        return False, "공급사 발주 API 없음 → 수동 발주"
    if not supplier.verified:
        return False, "미검증 공급사"
    if not supplier.auto_purchase_allowed:
        return False, "공급사 자동 발주 미허용"
    if supplier.auto_purchase_paused:
        return False, f"자동 발주 중단 상태: {supplier.pause_reason}"
    return True, ""


def process_paid_orders(db: Session, naver: NaverClient) -> dict:
    s = get_all_settings(db)
    summary = {"stock_ok": 0, "on_hold": 0, "auto_purchased": 0, "awaiting_approval": 0, "failed": 0}
    for order in db.query(Order).filter_by(status=S.PAID).order_by(Order.id).all():
        if order.product is None:
            continue
        if not check_stock(db, order, s):
            summary["on_hold"] += 1
            continue
        summary["stock_ok"] += 1
        po = get_or_create_purchase(db, order)
        ok, why = auto_purchase_allowed(order.supplier, s)
        if not ok:
            transition(db, order, S.AWAITING_APPROVAL, SYSTEM, why)
            summary["awaiting_approval"] += 1
            continue
        result = submit_purchase(db, naver, po, SYSTEM, s)
        summary["auto_purchased" if result in ("CONFIRMED", "REQUESTED") else
                "failed" if result in ("FAILED", "RETRY") else "on_hold"] += 1
    db.flush()
    return summary


def approve_purchase(db: Session, naver: NaverClient, po: PurchaseOrder, actor: str,
                     supplier_order_no: str | None = None) -> str:
    """관리자 발주 승인. supplier_order_no 를 주면 '수동 발주 완료' 기록(발주 API 없는 공급사)."""
    order = po.order
    if order.status not in (S.AWAITING_APPROVAL, S.ON_HOLD, S.STOCK_CHECKED):
        raise ValueError(f"발주 승인 불가 상태: {order.status.value}")
    po.approved_by = actor
    audit(db, actor, "purchase.approve", "purchase_order", po.id, manual_no=supplier_order_no)
    if supplier_order_no:
        transition(db, order, S.PURCHASE_REQUESTED, actor, "수동 발주")
        po.supplier_order_no, po.status, po.dry_run = supplier_order_no, P.CONFIRMED, False
        transition(db, order, S.SUPPLIER_CONFIRMED, actor, f"공급사 발주번호 {supplier_order_no}")
        _confirm_on_naver(db, naver, order)
        return "CONFIRMED"
    return submit_purchase(db, naver, po, actor, get_all_settings(db))


def submit_purchase(db: Session, naver: NaverClient, po: PurchaseOrder, actor: str, s: dict) -> str:
    """공급사 발주 1회 시도. 반환: CONFIRMED | REQUESTED | RETRY | FAILED | DRY_RUN | LIMIT | DUPLICATE."""
    cfg = get_settings()
    order, supplier = po.order, po.supplier
    if po.supplier_order_no and po.status in (P.REQUESTED, P.CONFIRMED, P.SHIPPED):
        return "DUPLICATE"  # 이미 발주됨 → 중복 발주 방지
    adapter = get_adapter(supplier)
    if not adapter.supports_purchase:
        raise PurchaseNotSupported("발주 API 미지원: 공급사 사이트/연락으로 발주 후 발주번호를 입력하세요")

    limit = Decimal(str(s["daily_purchase_amount_limit"]))
    if adapter.is_live and purchased_amount_today(db) + po.amount > limit:
        transition(db, order, S.ON_HOLD, SYSTEM, f"일일 발주 금액 한도 초과 ({limit})")
        raise_alert(db, "error", "purchase_limit", f"일일 발주 한도 초과로 보류: {order.naver_product_order_id}")
        return "LIMIT"

    pii_ok = adapter.is_live and cfg.allow_pii_transfer and supplier.pii_transfer_agreed
    name, phone, addr = decrypt_pii(order.buyer_name_enc), decrypt_pii(order.buyer_phone_enc), decrypt_pii(order.address_enc)
    recipient = ({"name": name, "phone": phone, "address": addr} if pii_ok else
                 {"name": mask_name(name), "phone": mask_phone(phone), "address": mask_address(addr), "masked": True})
    sku = order.product.supplier_product.supplier_sku
    req = PurchaseRequest(idempotency_key=po.idempotency_key, sku=sku, option_sku=None, quantity=order.quantity,
                          recipient=recipient, attempt=po.attempts + 1)

    if adapter.is_live and not cfg.allow_real_purchase:
        po.dry_run, po.last_error = True, "ALLOW_REAL_PURCHASE=false → Dry-run (공급사 호출 안 함)"
        audit(db, actor, "purchase.dry_run", "purchase_order", po.id, sku=sku, qty=order.quantity, masked=not pii_ok)
        if order.status != S.AWAITING_APPROVAL:
            transition(db, order, S.AWAITING_APPROVAL, SYSTEM, "Dry-run: 실제 발주 비활성")
        return "DRY_RUN"

    if order.status != S.PURCHASE_REQUESTED:
        transition(db, order, S.PURCHASE_REQUESTED, actor, f"발주 요청 (시도 {req.attempt})")
    po.status, po.attempts = P.REQUESTING, po.attempts + 1
    po.dry_run = False
    try:
        res = adapter.place_order(req)
    except AdapterError as e:
        po.last_error = str(e)
        max_retries = int(s["max_purchase_retries"])
        if po.attempts >= max_retries:
            po.status = P.FAILED
            transition(db, order, S.FAILED, SYSTEM, f"발주 {po.attempts}회 실패: {e}")
            dead_letter(db, "submit_purchase", {"purchase_order_id": po.id, "order": order.naver_product_order_id},
                        str(e), po.attempts)
            return "FAILED"
        log.warning("purchase.retry", po=po.id, attempt=po.attempts, error=str(e))
        return "RETRY"
    po.supplier_order_no, po.last_error = res.supplier_order_no, None
    po.status = P.CONFIRMED if res.status == "CONFIRMED" else P.REQUESTED
    if po.status == P.CONFIRMED:
        transition(db, order, S.SUPPLIER_CONFIRMED, SYSTEM, f"공급사 발주번호 {res.supplier_order_no}")
        _confirm_on_naver(db, naver, order)
    return po.status.value


def retry_pending_purchases(db: Session, naver: NaverClient) -> dict:
    s = get_all_settings(db)
    out = {"retried": 0}
    for po in db.query(PurchaseOrder).filter_by(status=P.REQUESTING).all():
        submit_purchase(db, naver, po, SYSTEM, s)
        out["retried"] += 1
    return out


def _confirm_on_naver(db: Session, naver: NaverClient, order: Order) -> None:
    try:
        naver.confirm_orders([order.naver_product_order_id])  # 네이버 발주확인
    except NaverApiError as e:
        raise_alert(db, "warning", "naver", f"발주확인 실패 {order.naver_product_order_id}: {e}")


# --------------------------------------------------------------------- 송장/발송


def register_tracking(db: Session, naver: NaverClient, po: PurchaseOrder, carrier_code: str, tracking_no: str,
                      actor: str, s: dict | None = None) -> bool:
    s = s or get_all_settings(db)
    order = po.order
    naver_code = map_carrier(carrier_code, s.get("carrier_code_map"))
    po.carrier_code, po.tracking_no, po.naver_carrier_code = carrier_code, tracking_no, naver_code
    if order.status == S.SUPPLIER_CONFIRMED:
        transition(db, order, S.SHIPPED, actor, f"송장 {carrier_code} {tracking_no}")
    po.status = P.SHIPPED
    if not naver_code:
        raise_alert(db, "warning", "carrier", f"택배사 코드 매핑 없음: '{carrier_code}' (주문 {order.naver_product_order_id})")
        return False
    try:
        naver.dispatch(order.naver_product_order_id, naver_code, tracking_no)
    except NaverApiError as e:
        raise_alert(db, "error", "naver", f"발송처리 실패 {order.naver_product_order_id}: {e}")
        return False
    transition(db, order, S.TRACKING_REGISTERED, actor, f"네이버 발송처리 {naver_code} {tracking_no}")
    return True


def poll_shipments(db: Session, naver: NaverClient) -> dict:
    s = get_all_settings(db)
    out = {"checked": 0, "registered": 0, "pending": 0}
    pos = (db.query(PurchaseOrder).join(Order)
           .filter(PurchaseOrder.status.in_([P.REQUESTED, P.CONFIRMED]), Order.status == S.SUPPLIER_CONFIRMED).all())
    for po in pos:
        adapter = get_adapter(po.supplier)
        if not adapter.supports_purchase or not po.supplier_order_no:
            continue
        out["checked"] += 1
        try:
            info = adapter.get_shipment(po.supplier_order_no)
        except (AdapterError, PurchaseNotSupported) as e:
            log.warning("shipment.poll_failed", po=po.id, error=str(e))
            continue
        if info.status in ("SHIPPED", "DELIVERED") and info.tracking_no:
            if register_tracking(db, naver, po, info.carrier_code or "", info.tracking_no, SYSTEM, s):
                out["registered"] += 1
        else:
            out["pending"] += 1
    return out


# --------------------------------------------------------------------- 클레임


def handle_cancel(db: Session, naver: NaverClient, order: Order, actor: str) -> str:
    if order.status in (S.CANCELLED,):
        return "ALREADY"
    po = db.query(PurchaseOrder).filter_by(order_id=order.id).one_or_none()
    order.claim_type = "CANCEL"
    if order.status not in (S.CANCEL_REQUESTED,):
        transition(db, order, S.CANCEL_REQUESTED, actor, "취소 요청")
    if po is None or po.status in (P.PENDING_APPROVAL, P.FAILED) or po.dry_run:
        if po:
            po.status = P.CANCELLED
        naver.approve_claim(order.naver_product_order_id, "CANCEL")
        transition(db, order, S.CANCELLED, actor, "발주 전 취소 승인")
        return "CANCELLED"
    if po.status == P.SHIPPED:
        raise_alert(db, "warning", "claim", f"이미 출고된 주문 취소 요청 {order.naver_product_order_id}: 반품 전환 필요")
        return "MANUAL"
    adapter = get_adapter(po.supplier)
    try:
        if adapter.supports_purchase and po.supplier_order_no and adapter.cancel_order(po.supplier_order_no):
            po.status = P.CANCELLED
            naver.approve_claim(order.naver_product_order_id, "CANCEL")
            transition(db, order, S.CANCELLED, actor, "공급사 발주 취소 후 취소 승인")
            return "CANCELLED"
    except (AdapterError, PurchaseNotSupported) as e:
        log.warning("cancel.supplier_failed", error=str(e))
    raise_alert(db, "warning", "claim", f"공급사 발주 취소 수동 처리 필요 {order.naver_product_order_id}")
    return "MANUAL"


def approve_return(db: Session, naver: NaverClient, order: Order, actor: str) -> None:
    naver.approve_claim(order.naver_product_order_id, "RETURN")
    transition(db, order, S.RETURNED, actor, "반품 승인")


def approve_exchange_collect(db: Session, naver: NaverClient, order: Order, actor: str) -> None:
    """교환 수거 완료 처리 (네이버). 재배송 상품은 공급사에 별도 발주/요청 후 redispatch_exchange 로 송장 등록."""
    if order.status != S.EXCHANGE_REQUESTED:
        raise ValueError(f"교환 요청 상태가 아닙니다: {order.status.value}")
    if order.claim_status == "EXCHANGE_COLLECTED":
        return
    naver.approve_exchange_collect(order.naver_product_order_id)
    order.claim_status = "EXCHANGE_COLLECTED"
    db.add(OrderEvent(order_id=order.id, from_status=order.status.value, to_status=order.status.value, actor=actor,
                      reason="교환 수거 완료 (네이버 처리)"))


def redispatch_exchange(db: Session, naver: NaverClient, order: Order, carrier_code: str, tracking_no: str,
                        actor: str) -> bool:
    if order.status != S.EXCHANGE_REQUESTED or order.claim_status != "EXCHANGE_COLLECTED":
        raise ValueError("교환 수거 완료 후에만 재배송 송장을 등록할 수 있습니다")
    s = get_all_settings(db)
    naver_code = map_carrier(carrier_code, s.get("carrier_code_map"))
    if not naver_code:
        raise ValueError(f"택배사 코드 매핑 없음: '{carrier_code}'")
    naver.redispatch_exchange(order.naver_product_order_id, naver_code, tracking_no)
    order.claim_status = "EXCHANGE_REDISPATCHED"
    transition(db, order, S.TRACKING_REGISTERED, actor, f"교환 재배송 {naver_code} {tracking_no}")
    return True


def request_supplier_return(db: Session, order: Order, actor: str) -> str:
    """공급사 반품 접수. API 가 있으면 자동 접수, 없거나 실제 공급사인데 안전 스위치가 꺼져 있으면 수동 처리로 표시."""
    po = db.query(PurchaseOrder).filter_by(order_id=order.id).one_or_none()
    if po is None or not po.supplier_order_no:
        raise_alert(db, "warning", "claim", f"반품 요청 {order.naver_product_order_id}: 발주 기록 없음 → 수동 확인")
        return "NO_PURCHASE"
    if po.return_status == "REQUESTED":
        return "ALREADY"
    adapter = get_adapter(po.supplier)
    if adapter.is_live and not get_settings().allow_real_purchase:
        po.return_status = "MANUAL_REQUIRED"
        raise_alert(db, "warning", "claim", f"반품 요청 {order.naver_product_order_id}: 실제 공급사 호출 비활성 → 수동 반품 접수")
        return "MANUAL_REQUIRED"
    try:
        po.supplier_return_no = adapter.request_return(po.supplier_order_no, "고객 반품")
        po.return_status = "REQUESTED"
        audit(db, actor, "purchase.return_request", "purchase_order", po.id, return_no=po.supplier_return_no)
        return "REQUESTED"
    except (AdapterError, PurchaseNotSupported) as e:
        po.return_status = "MANUAL_REQUIRED"
        raise_alert(db, "warning", "claim", f"반품 요청 {order.naver_product_order_id}: 공급사 반품 수동 접수 필요 ({e})")
        return "MANUAL_REQUIRED"
