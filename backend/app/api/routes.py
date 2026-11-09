from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.deps import Principal, admin, operator, viewer
from app.api.serializers import order_dict, to_dict
from app.config import get_settings
from app.db import get_db
from app.jobs import JOBS, run_job, run_pipeline
from app.models import (
    Alert, ApiCallLog, AuditLog, DeadLetter, JobRun, Order, OrderEvent, OrderStatus, Product, ProductStatus,
    PurchaseOrder, PurchaseStatus, Role, Supplier, SupplierProduct, User,
)
from app.naver.client import NaverApiError, get_naver_client
from app.security import (
    create_access_token, decrypt_pii, encrypt_pii, hash_password, new_totp_secret, totp_uri, verify_password, verify_totp,
)
from app.services import analytics, fulfillment, listing, mock_sim, pricing, sourcing
from app.services.alerts import audit
from app.services.order_state import InvalidTransition, transition
from app.services.settings_service import get_all_settings, update_settings

router = APIRouter(prefix="/api")


def _404(obj, what="대상"):
    if obj is None:
        raise HTTPException(404, f"{what}을(를) 찾을 수 없습니다")
    return obj


class TrackingIn(BaseModel):
    carrier_code: str
    tracking_no: str = Field(min_length=6, max_length=40)


# ------------------------------------------------------------------ 인증/사용자


class LoginIn(BaseModel):
    email: EmailStr
    password: str
    otp: str | None = None


MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15


@router.post("/auth/login", tags=["auth"])
def login(body: LoginIn, db: Session = Depends(get_db)):
    from datetime import timedelta, timezone

    from app.models import utcnow

    user = db.query(User).filter_by(email=body.email, active=True).one_or_none()
    now = utcnow()
    if user is not None and user.locked_until is not None:
        locked = user.locked_until if user.locked_until.tzinfo else user.locked_until.replace(tzinfo=timezone.utc)
        if locked > now:
            raise HTTPException(429, f"로그인 시도 초과로 잠김. {int((locked - now).total_seconds() // 60) + 1}분 후 다시 시도하세요")
    password_ok = user is not None and verify_password(body.password, user.password_hash)
    if password_ok and user.totp_enabled and not body.otp:
        raise HTTPException(401, "OTP_REQUIRED")  # 비밀번호는 맞음 → 2단계 코드 입력 요청 (실패 횟수 미증가)
    otp_ok = (not password_ok) or (not user.totp_enabled) or verify_totp(decrypt_pii(user.totp_secret_enc) or "", body.otp)
    if not password_ok or not otp_ok:
        if user is not None:
            user.failed_logins = (user.failed_logins or 0) + 1
            if user.failed_logins >= MAX_FAILED_LOGINS:
                user.locked_until, user.failed_logins = now + timedelta(minutes=LOCK_MINUTES), 0
                audit(db, user.email, "auth.locked", "user", user.email)
            db.commit()
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다")
    user.failed_logins, user.locked_until = 0, None
    db.commit()
    return {"access_token": create_access_token(user.email, user.role), "role": user.role.value, "email": user.email,
            "password_change_recommended": user.password_changed_at is None}


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


@router.post("/auth/password", tags=["auth"])
def change_password(body: PasswordIn, db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    from app.models import utcnow

    user = db.query(User).filter_by(email=p.email).one_or_none()
    if user is None:
        raise HTTPException(403, "서비스 토큰으로는 비밀번호를 변경할 수 없습니다")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "현재 비밀번호가 올바르지 않습니다")
    if body.current_password == body.new_password:
        raise HTTPException(400, "새 비밀번호가 기존과 같습니다")
    user.password_hash, user.password_changed_at = hash_password(body.new_password), utcnow()
    audit(db, p.email, "auth.password_change", "user", p.email)
    db.commit()
    return {"ok": True}


@router.get("/auth/me", tags=["auth"])
def me(db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    user = db.query(User).filter_by(email=p.email).one_or_none()
    return {"email": p.email, "role": p.role.value, "totp_enabled": bool(user and user.totp_enabled)}


class OtpIn(BaseModel):
    code: str


class OtpDisableIn(BaseModel):
    password: str
    code: str


def _self_user(db: Session, p: Principal) -> User:
    user = db.query(User).filter_by(email=p.email).one_or_none()
    if user is None:
        raise HTTPException(403, "사용자 계정만 사용할 수 있습니다")
    return user


@router.post("/auth/2fa/setup", tags=["auth"])
def otp_setup(db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    """OTP 비밀키 발급(아직 비활성). 인증 앱에 등록 후 /auth/2fa/enable 로 코드 확인."""
    user = _self_user(db, p)
    if user.totp_enabled:
        raise HTTPException(409, "이미 2단계 인증이 켜져 있습니다")
    secret = new_totp_secret()
    user.totp_secret_enc = encrypt_pii(secret)
    db.commit()
    return {"secret": secret, "otpauth_uri": totp_uri(secret, user.email)}


@router.post("/auth/2fa/enable", tags=["auth"])
def otp_enable(body: OtpIn, db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    user = _self_user(db, p)
    secret = decrypt_pii(user.totp_secret_enc)
    if not secret or not verify_totp(secret, body.code):
        raise HTTPException(400, "OTP 코드가 올바르지 않습니다")
    user.totp_enabled = True
    audit(db, p.email, "auth.2fa_enable", "user", p.email)
    db.commit()
    return {"totp_enabled": True}


@router.post("/auth/2fa/disable", tags=["auth"])
def otp_disable(body: OtpDisableIn, db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    user = _self_user(db, p)
    if not verify_password(body.password, user.password_hash) or not verify_totp(decrypt_pii(user.totp_secret_enc) or "", body.code):
        raise HTTPException(400, "비밀번호 또는 OTP 코드가 올바르지 않습니다")
    user.totp_enabled, user.totp_secret_enc = False, None
    audit(db, p.email, "auth.2fa_disable", "user", p.email)
    db.commit()
    return {"totp_enabled": False}


class UserIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10)
    role: Role = Role.VIEWER


USER_HIDDEN = {"password_hash", "totp_secret_enc"}


@router.get("/users", tags=["auth"])
def list_users(db: Session = Depends(get_db), p: Principal = Depends(admin)):
    return [to_dict(u, exclude=USER_HIDDEN) for u in db.query(User).order_by(User.id)]


class UserPatch(BaseModel):
    role: Role | None = None
    active: bool | None = None
    unlock: bool = False
    reset_2fa: bool = False
    reset_password: str | None = Field(default=None, min_length=10, max_length=128)


@router.patch("/users/{uid}", tags=["auth"])
def patch_user(uid: int, body: UserPatch, db: Session = Depends(get_db), p: Principal = Depends(admin)):
    u = _404(db.get(User, uid), "사용자")
    if u.email == p.email and (body.active is False or (body.role and body.role != Role.ADMIN)):
        raise HTTPException(409, "자기 자신의 비활성화/권한 강등은 할 수 없습니다")
    changes: dict = {}
    if body.role is not None:
        u.role, changes["role"] = body.role, body.role.value
    if body.active is not None:
        u.active, changes["active"] = body.active, body.active
    if body.unlock:
        u.failed_logins, u.locked_until, changes["unlock"] = 0, None, True
    if body.reset_2fa:
        u.totp_enabled, u.totp_secret_enc, changes["reset_2fa"] = False, None, True
    if body.reset_password:
        u.password_hash, u.password_changed_at, changes["reset_password"] = hash_password(body.reset_password), None, True
    audit(db, p.email, "user.update", "user", u.email, **{k: str(v) for k, v in changes.items()})
    db.commit()
    return to_dict(u, exclude=USER_HIDDEN)


@router.post("/users", tags=["auth"])
def create_user(body: UserIn, db: Session = Depends(get_db), p: Principal = Depends(admin)):
    if db.query(User).filter_by(email=body.email).first():
        raise HTTPException(409, "이미 존재하는 사용자")
    u = User(email=body.email, password_hash=hash_password(body.password), role=body.role)
    db.add(u)
    audit(db, p.email, "user.create", "user", body.email, role=body.role.value)
    db.commit()
    return to_dict(u, exclude=USER_HIDDEN)


# ------------------------------------------------------------------ 대시보드/분석


@router.get("/dashboard", tags=["dashboard"])
def get_dashboard(db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    return analytics.dashboard(db)


@router.get("/analytics/revenue", tags=["analytics"])
def get_revenue(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    return analytics.revenue(db, days)


# ------------------------------------------------------------------ 공급사


class SupplierIn(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{2,50}$")
    name: str
    adapter_type: str = "mock"
    config: dict = {}
    authorized_brands: list[str] = []
    image_usage_allowed: bool = False
    contract_note: str | None = None


class SupplierPatch(BaseModel):
    name: str | None = None
    active: bool | None = None
    config: dict | None = None
    verified: bool | None = None
    auto_listing_allowed: bool | None = None
    auto_purchase_allowed: bool | None = None
    auto_purchase_paused: bool | None = None
    purchase_api_available: bool | None = None
    pii_transfer_agreed: bool | None = None
    image_usage_allowed: bool | None = None
    authorized_brands: list[str] | None = None
    contract_note: str | None = None


@router.get("/suppliers", tags=["suppliers"])
def list_suppliers(db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    out = []
    for s in db.query(Supplier).order_by(Supplier.id):
        d = to_dict(s)
        d["product_count"] = db.query(SupplierProduct).filter_by(supplier_id=s.id).count()
        out.append(d)
    return out


@router.post("/suppliers", tags=["suppliers"])
def create_supplier(body: SupplierIn, db: Session = Depends(get_db), p: Principal = Depends(admin)):
    if db.query(Supplier).filter_by(code=body.code).first():
        raise HTTPException(409, "이미 존재하는 공급사 코드")
    s = Supplier(**body.model_dump())
    db.add(s)
    audit(db, p.email, "supplier.create", "supplier", body.code)
    db.commit()
    return to_dict(s)


@router.patch("/suppliers/{sid}", tags=["suppliers"])
def patch_supplier(sid: int, body: SupplierPatch, db: Session = Depends(get_db), p: Principal = Depends(admin)):
    s = _404(db.get(Supplier, sid), "공급사")
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(s, k, v)
    if changes.get("auto_purchase_paused") is False:
        s.pause_reason = None
    audit(db, p.email, "supplier.update", "supplier", s.code, **{k: str(v) for k, v in changes.items()})
    db.commit()
    return to_dict(s)


@router.post("/suppliers/{sid}/sync", tags=["suppliers"])
def sync_supplier(sid: int, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    s = _404(db.get(Supplier, sid), "공급사")
    result = sourcing.sync_supplier(db, s)
    result["processed"] = listing.process_new_candidates(db)
    db.commit()
    return result


@router.get("/sourcing", tags=["sourcing"])
def list_supplier_products(status: str | None = None, supplier_id: int | None = None, db: Session = Depends(get_db),
                           p: Principal = Depends(viewer)):
    q = db.query(SupplierProduct).order_by(SupplierProduct.id.desc())
    if status:
        q = q.filter(SupplierProduct.status == status)
    if supplier_id:
        q = q.filter(SupplierProduct.supplier_id == supplier_id)
    out = []
    for sp in q.limit(500):
        d = to_dict(sp)
        d["supplier_code"] = sp.supplier.code
        pr = db.query(Product).filter_by(supplier_product_id=sp.id).one_or_none()
        d["product_id"], d["product_status"] = (pr.id, pr.status.value) if pr else (None, None)
        out.append(d)
    return out


# ------------------------------------------------------------------ 상품


def _product_dict(pr: Product) -> dict:
    d = to_dict(pr, exclude={"detail_html"})
    sp = pr.supplier_product
    d.update(supplier_code=pr.supplier.code, supplier_sku=sp.supplier_sku, supply_price=str(sp.supply_price),
             supplier_shipping_fee=str(sp.shipping_fee), supplier_stock=sp.stock, source_name=sp.name,
             image=(sp.images or [None])[0])
    return d


@router.get("/products", tags=["products"])
def list_products(status: str | None = None, db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    q = db.query(Product).order_by(Product.id.desc())
    if status:
        q = q.filter(Product.status.in_(status.split(",")))
    return [_product_dict(pr) for pr in q.limit(500)]


@router.get("/products/{pid}", tags=["products"])
def get_product(pid: int, db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    pr = _404(db.get(Product, pid), "상품")
    d = _product_dict(pr)
    d["detail_html"] = pr.detail_html
    d["source"] = to_dict(pr.supplier_product)
    d["api_logs"] = [to_dict(l) for l in db.query(ApiCallLog).filter_by(entity_id=pr.listing_key)
                     .order_by(ApiCallLog.id.desc()).limit(20)]
    return d


class ProductPatch(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = None
    category_id: str | None = None
    category_name: str | None = None


@router.patch("/products/{pid}", tags=["products"])
def patch_product(pid: int, body: ProductPatch, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    pr = _404(db.get(Product, pid), "상품")
    if pr.status == ProductStatus.LISTED:
        raise HTTPException(409, "등록된 상품은 판매중지 후 수정하세요")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(pr, k, v)
    if body.category_id:
        pr.block_reasons = [b for b in pr.block_reasons if b != "CATEGORY_REQUIRED"]
    audit(db, p.email, "product.edit", "product", pid, **body.model_dump(exclude_unset=True))
    db.commit()
    return _product_dict(pr)


class ApproveIn(BaseModel):
    sale_price: Decimal | None = None


@router.post("/products/{pid}/approve", tags=["products"])
def approve_product(pid: int, body: ApproveIn | None = None, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    pr = _404(db.get(Product, pid), "상품")
    try:
        listing.approve_product(db, pr, p.email, body.sale_price if body else None)
    except ValueError as e:
        db.commit()  # 가격 재평가 결과는 저장
        raise HTTPException(422, str(e)) from e
    db.commit()
    return _product_dict(pr)


@router.post("/products/{pid}/reject", tags=["products"])
def reject_product(pid: int, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    pr = _404(db.get(Product, pid), "상품")
    if pr.status == ProductStatus.LISTED:
        raise HTTPException(409, "등록된 상품은 판매중지를 사용하세요")
    pr.status = ProductStatus.BLOCKED
    pr.block_reasons = list(pr.block_reasons) + [f"REJECTED_BY:{p.email}"]
    audit(db, p.email, "product.reject", "product", pid)
    db.commit()
    return _product_dict(pr)


@router.post("/products/{pid}/reprocess", tags=["products"])
def reprocess_product(pid: int, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    pr = _404(db.get(Product, pid), "상품")
    if pr.status in (ProductStatus.LISTED, ProductStatus.APPROVED):
        raise HTTPException(409, "등록/승인된 상품은 재가공할 수 없습니다")
    listing.process_supplier_product(db, pr.supplier_product)
    db.commit()
    return _product_dict(pr)


@router.post("/products/{pid}/suspend", tags=["products"])
def suspend(pid: int, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    pr = _404(db.get(Product, pid), "상품")
    listing.suspend_product(db, get_naver_client(db), pr, p.email)
    db.commit()
    return _product_dict(pr)


@router.post("/products/{pid}/resume", tags=["products"])
def resume(pid: int, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    pr = _404(db.get(Product, pid), "상품")
    if pr.status != ProductStatus.SUSPENDED or not pr.naver_origin_product_no:
        raise HTTPException(409, "판매중지된 등록 상품만 재개할 수 있습니다")
    get_naver_client(db).change_status(pr.naver_origin_product_no, "SALE", pr.stock)
    pr.status = ProductStatus.LISTED
    audit(db, p.email, "product.resume", "product", pid)
    db.commit()
    return _product_dict(pr)


class SimIn(BaseModel):
    supply_price: Decimal
    shipping_fee: Decimal = Decimal(0)
    sale_price: Decimal | None = None


@router.post("/pricing/simulate", tags=["pricing"])
def simulate_price(body: SimIn, db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    cfg = pricing.PricingConfig.from_settings(get_all_settings(db))
    suggested = pricing.suggest_price(body.supply_price, body.shipping_fee, cfg)
    out: dict[str, Any] = {"suggested": {**suggested.breakdown(), "ok": suggested.ok, "reasons": suggested.reasons}}
    if body.sale_price is not None:
        ev = pricing.evaluate(body.sale_price, body.supply_price, body.shipping_fee, cfg)
        out["evaluated"] = {**ev.breakdown(), "ok": ev.ok, "reasons": ev.reasons}
    return out


@router.get("/inventory", tags=["inventory"])
def inventory(db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    q = db.query(Product).filter(Product.status.in_([ProductStatus.LISTED, ProductStatus.SOLD_OUT, ProductStatus.SUSPENDED]))
    return [{**_product_dict(pr), "mismatch": pr.stock != pr.supplier_product.stock} for pr in q]


# ------------------------------------------------------------------ 주문/발주/배송


@router.get("/orders", tags=["orders"])
def list_orders(status: str | None = None, db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    q = db.query(Order).order_by(Order.id.desc())
    if status:
        q = q.filter(Order.status.in_(status.split(",")))
    return [order_dict(o) for o in q.limit(500)]


@router.get("/orders/{oid}", tags=["orders"])
def get_order(oid: int, reveal: bool = False, db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    o = _404(db.get(Order, oid), "주문")
    if reveal:
        if p.role != Role.ADMIN:
            raise HTTPException(403, "개인정보 열람은 admin 권한 필요")
        audit(db, p.email, "pii.reveal", "order", oid)
        db.commit()
    d = order_dict(o, reveal=reveal)
    d["events"] = [to_dict(e) for e in db.query(OrderEvent).filter_by(order_id=oid).order_by(OrderEvent.id)]
    po = db.query(PurchaseOrder).filter_by(order_id=oid).one_or_none()
    d["purchase"] = to_dict(po) if po else None
    return d


@router.post("/orders/{oid}/release-hold", tags=["orders"])
def release_hold(oid: int, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    o = _404(db.get(Order, oid), "주문")
    if o.status != OrderStatus.ON_HOLD:
        raise HTTPException(409, "보류 상태가 아닙니다")
    po = db.query(PurchaseOrder).filter_by(order_id=oid).one_or_none()
    target = OrderStatus.AWAITING_APPROVAL if po else OrderStatus.PAID
    transition(db, o, target, p.email, "관리자 보류 해제")
    db.commit()
    return order_dict(o)


@router.post("/orders/{oid}/cancel", tags=["orders"])
def cancel_order(oid: int, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    o = _404(db.get(Order, oid), "주문")
    try:
        result = fulfillment.handle_cancel(db, get_naver_client(db), o, p.email)
    except InvalidTransition as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return {"result": result, "order": order_dict(o)}


@router.post("/orders/{oid}/exchange/collect-approve", tags=["orders"])
def exchange_collect(oid: int, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    o = _404(db.get(Order, oid), "주문")
    try:
        fulfillment.approve_exchange_collect(db, get_naver_client(db), o, p.email)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return order_dict(o)


@router.post("/orders/{oid}/exchange/redispatch", tags=["orders"])
def exchange_redispatch(oid: int, body: TrackingIn, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    o = _404(db.get(Order, oid), "주문")
    try:
        fulfillment.redispatch_exchange(db, get_naver_client(db), o, body.carrier_code, body.tracking_no, p.email)
    except (ValueError, InvalidTransition) as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return order_dict(o)


@router.post("/orders/{oid}/approve-return", tags=["orders"])
def approve_return(oid: int, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    o = _404(db.get(Order, oid), "주문")
    try:
        fulfillment.approve_return(db, get_naver_client(db), o, p.email)
    except InvalidTransition as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return order_dict(o)


def _po_dict(po: PurchaseOrder) -> dict:
    d = to_dict(po)
    d["order"] = order_dict(po.order)
    d["supplier_code"] = po.supplier.code
    return d


@router.get("/purchases", tags=["purchases"])
def list_purchases(status: str | None = None, db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    q = db.query(PurchaseOrder).order_by(PurchaseOrder.id.desc())
    if status:
        q = q.filter(PurchaseOrder.status.in_(status.split(",")))
    return [_po_dict(po) for po in q.limit(500)]


class PurchaseApproveIn(BaseModel):
    supplier_order_no: str | None = None


@router.post("/purchases/{poid}/approve", tags=["purchases"])
def approve_purchase(poid: int, body: PurchaseApproveIn | None = None, db: Session = Depends(get_db),
                     p: Principal = Depends(operator)):
    po = _404(db.get(PurchaseOrder, poid), "발주")
    try:
        result = fulfillment.approve_purchase(db, get_naver_client(db), po, p.email,
                                              body.supplier_order_no if body else None)
    except (ValueError, InvalidTransition) as e:
        raise HTTPException(409, str(e)) from e
    except fulfillment.PurchaseNotSupported as e:
        raise HTTPException(422, str(e)) from e
    db.commit()
    return {"result": result, "purchase": _po_dict(po)}


@router.post("/purchases/{poid}/tracking", tags=["shipping"])
def add_tracking(poid: int, body: TrackingIn, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    po = _404(db.get(PurchaseOrder, poid), "발주")
    if po.order.status not in (OrderStatus.SUPPLIER_CONFIRMED, OrderStatus.SHIPPED):
        raise HTTPException(409, f"송장 등록 불가 상태: {po.order.status.value}")
    ok = fulfillment.register_tracking(db, get_naver_client(db), po, body.carrier_code, body.tracking_no, p.email)
    db.commit()
    return {"dispatched": ok, "purchase": _po_dict(po)}


@router.get("/shipments", tags=["shipping"])
def shipments(db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    states = [OrderStatus.SUPPLIER_CONFIRMED, OrderStatus.SHIPPED, OrderStatus.TRACKING_REGISTERED, OrderStatus.DELIVERED]
    rows = (db.query(PurchaseOrder).join(Order).filter(Order.status.in_(states)).order_by(PurchaseOrder.id.desc()).limit(500))
    return [_po_dict(po) for po in rows]


@router.get("/settlements", tags=["analytics"])
def list_settlements(mismatch_only: bool = False, db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    from app.models import Settlement

    q = db.query(Settlement).order_by(Settlement.id.desc())
    if mismatch_only:
        q = q.filter(Settlement.mismatch.is_(True))
    return [to_dict(x, exclude={"raw"}) for x in q.limit(500)]


@router.get("/categories", tags=["products"])
def search_categories(q: str = "", limit: int = Query(30, le=200), db: Session = Depends(get_db),
                      p: Principal = Depends(viewer)):
    from app.services.categories import load_category_map

    cats = load_category_map(db)
    words = q.split()
    hits = [{"id": cid, "whole_name": name} for name, cid in cats.items() if all(w in name for w in words)]
    return {"total": len(cats), "items": hits[:limit]}


# ------------------------------------------------------------------ 오류/알림/로그


@router.get("/alerts", tags=["alerts"])
def list_alerts(open_only: bool = False, db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    q = db.query(Alert).order_by(Alert.id.desc())
    if open_only:
        q = q.filter_by(acknowledged=False)
    return [to_dict(a) for a in q.limit(300)]


@router.post("/alerts/{aid}/ack", tags=["alerts"])
def ack_alert(aid: int, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    a = _404(db.get(Alert, aid), "알림")
    a.acknowledged = True
    db.commit()
    return to_dict(a)


@router.get("/dead-letters", tags=["alerts"])
def list_dlq(db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    return [to_dict(d) for d in db.query(DeadLetter).order_by(DeadLetter.id.desc()).limit(300)]


@router.post("/dead-letters/{did}/resolve", tags=["alerts"])
def resolve_dlq(did: int, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    d = _404(db.get(DeadLetter, did), "DLQ 항목")
    d.resolved = True
    audit(db, p.email, "dlq.resolve", "dead_letter", did)
    db.commit()
    return to_dict(d)


@router.get("/api-logs", tags=["alerts"])
def api_logs(db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    return [to_dict(l) for l in db.query(ApiCallLog).order_by(ApiCallLog.id.desc()).limit(300)]


@router.get("/audit-logs", tags=["alerts"])
def audit_logs(db: Session = Depends(get_db), p: Principal = Depends(admin)):
    return [to_dict(l) for l in db.query(AuditLog).order_by(AuditLog.id.desc()).limit(300)]


@router.get("/job-runs", tags=["automation"])
def job_runs(db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    return [to_dict(j) for j in db.query(JobRun).order_by(JobRun.id.desc()).limit(200)]


# ------------------------------------------------------------------ 설정/연결


@router.get("/settings", tags=["automation"])
def read_settings(db: Session = Depends(get_db), p: Principal = Depends(viewer)):
    return get_all_settings(db)


@router.put("/settings", tags=["automation"])
def write_settings(values: dict[str, Any], db: Session = Depends(get_db), p: Principal = Depends(admin)):
    try:
        out = update_settings(db, values, p.email)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    db.commit()
    return out


@router.get("/connections", tags=["connections"])
def connections(p: Principal = Depends(viewer)):
    s = get_settings()
    return {
        "naver": {"mode": s.naver_mode, "base_url": s.naver_base_url, "client_id_set": bool(s.naver_client_id),
                  "client_secret_set": bool(s.naver_client_secret), "token_type": s.naver_token_type, "rps": s.naver_rps},
        "safety": {"allow_public_listing": s.allow_public_listing, "allow_real_purchase": s.allow_real_purchase,
                   "allow_pii_transfer": s.allow_pii_transfer, "allow_naver_order_actions": s.allow_naver_order_actions},
        "claude": {"api_key_set": bool(s.anthropic_api_key), "model": s.claude_model, "enabled": s.ai_enabled},
        "monitoring": {"sentry": bool(s.sentry_dsn), "alert_webhook": bool(s.alert_webhook_url)},
        "categories": _category_status(),
        "note": "비밀값은 환경변수/Secret Manager 로만 설정합니다 (화면에서 입력/표시하지 않음).",
    }


def _category_status() -> dict:
    from sqlalchemy import func

    from app.db import SessionLocal
    from app.models import NaverCategory

    with SessionLocal() as db:
        n, last = db.query(func.count(NaverCategory.id), func.max(NaverCategory.synced_at)).one()
    return {"synced_count": n, "last_synced_at": last.isoformat() if last else None,
            "source": "네이버 동기화" if n else "Mock 카테고리 사전 (동기화 전)"}


@router.post("/connections/naver/test", tags=["connections"])
def test_naver(db: Session = Depends(get_db), p: Principal = Depends(admin)):
    """읽기 전용 호출(토큰 발급)만 수행해 인증정보를 검증한다."""
    s = get_settings()
    if s.naver_mode != "live":
        return {"ok": True, "mode": "mock", "message": "Mock 모드: 외부 호출 없음"}
    try:
        from app.naver.client import LiveNaverClient

        LiveNaverClient(db).tokens.get()
        return {"ok": True, "mode": "live", "message": "토큰 발급 성공"}
    except NaverApiError as e:
        return {"ok": False, "mode": "live", "message": str(e), "body": e.body}


# ------------------------------------------------------------------ 작업 실행


@router.post("/jobs/{name}/run", tags=["automation"])
def run(name: str, p: Principal = Depends(operator)):
    if name == "pipeline":
        return run_pipeline()
    if name not in JOBS:
        raise HTTPException(404, f"알 수 없는 작업: {name}")
    return run_job(name)


# ------------------------------------------------------------------ Mock 시뮬레이션


def _mock_only():
    if get_settings().naver_mode != "mock":
        raise HTTPException(403, "NAVER_MODE=mock 에서만 사용 가능")


class MockOrderIn(BaseModel):
    product_id: int
    quantity: int = Field(1, ge=1, le=20)


@router.post("/mock/orders", tags=["mock"])
def mock_order(body: MockOrderIn, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    _mock_only()
    pr = _404(db.get(Product, body.product_id), "상품")
    try:
        row = mock_sim.simulate_order(db, pr, body.quantity)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return {"product_order_id": row.product_order_id}


class MockStatusIn(BaseModel):
    status: str
    claim_type: str | None = None


@router.post("/mock/orders/{product_order_id}/status", tags=["mock"])
def mock_status(product_order_id: str, body: MockStatusIn, db: Session = Depends(get_db), p: Principal = Depends(operator)):
    _mock_only()
    row = mock_sim.set_mock_status(db, product_order_id, body.status, body.claim_type)
    db.commit()
    return {"product_order_id": row.product_order_id, "status": row.status}
