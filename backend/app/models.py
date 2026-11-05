"""DB 모델. PostgreSQL 운영, 테스트는 SQLite 호환."""
from __future__ import annotations

import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


Money = Numeric(14, 2)


class Role(str, enum.Enum):
    ADMIN = "admin"        # 전체 권한 (설정, API 연결, 사용자, 개인정보 열람)
    OPERATOR = "operator"  # 등록 승인, 발주 승인, 송장 입력
    VIEWER = "viewer"      # 조회 전용


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=20), default=Role.VIEWER)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    adapter_type: Mapped[str] = mapped_column(String(30), default="mock")  # mock | csv | api
    config: Mapped[dict] = mapped_column(JSON, default=dict)  # 비밀값 금지 (환경변수 이름만 저장)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # 단계적 자동화 게이트
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_listing_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_purchase_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_purchase_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    pause_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    purchase_api_available: Mapped[bool] = mapped_column(Boolean, default=False)
    # 계약/권리
    pii_transfer_agreed: Mapped[bool] = mapped_column(Boolean, default=False)
    image_usage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    authorized_brands: Mapped[list] = mapped_column(JSON, default=list)
    contract_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SupplierProductStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SOLD_OUT = "SOLD_OUT"
    DISCONTINUED = "DISCONTINUED"
    DUPLICATE = "DUPLICATE"


class SupplierProduct(Base):
    __tablename__ = "supplier_products"
    __table_args__ = (UniqueConstraint("supplier_id", "supplier_sku", name="uq_supplier_sku"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    supplier_sku: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(500))
    brand: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category_hint: Mapped[str | None] = mapped_column(String(300), nullable=True)
    supply_price: Mapped[Decimal] = mapped_column(Money)
    shipping_fee: Mapped[Decimal] = mapped_column(Money, default=0)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    options: Mapped[list] = mapped_column(JSON, default=list)
    images: Mapped[list] = mapped_column(JSON, default=list)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)  # 원산지, 제조사, 소재, 인증, 고시정보 등 원본 사실
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[SupplierProductStatus] = mapped_column(
        Enum(SupplierProductStatus, native_enum=False, length=20), default=SupplierProductStatus.ACTIVE
    )
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_products.id"), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    supplier: Mapped[Supplier] = relationship()


class ProductStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    BLOCKED = "BLOCKED"                    # 정책/마진 미달로 등록 차단
    PENDING_APPROVAL = "PENDING_APPROVAL"  # 관리자 승인 대기
    APPROVED = "APPROVED"                  # 승인됨 → 등록 큐
    LISTED = "LISTED"
    FAILED = "FAILED"
    SUSPENDED = "SUSPENDED"                # 판매중지
    SOLD_OUT = "SOLD_OUT"


class Product(Base):
    """스마트스토어 등록 대상(가공 결과). supplier_product 와 1:1, listing_key로 중복 등록 방지."""

    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_product_id: Mapped[int] = mapped_column(ForeignKey("supplier_products.id"), unique=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    listing_key: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, native_enum=False, length=20), default=ProductStatus.DRAFT, index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    detail_html: Mapped[str] = mapped_column(Text, default="")
    options_normalized: Mapped[list] = mapped_column(JSON, default=list)
    notice: Mapped[dict] = mapped_column(JSON, default=dict)
    sale_price: Mapped[Decimal] = mapped_column(Money)
    expected_profit: Mapped[Decimal] = mapped_column(Money)
    margin_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    cost_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    block_reasons: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    ai_source: Mapped[str] = mapped_column(String(20), default="rule")
    stock: Mapped[int] = mapped_column(Integer, default=0)
    naver_origin_product_no: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    naver_channel_product_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    dry_run_listed: Mapped[bool] = mapped_column(Boolean, default=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    listed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    supplier_product: Mapped[SupplierProduct] = relationship()
    supplier: Mapped[Supplier] = relationship()


class ApiCallLog(Base):
    """외부 API 호출 기록 (등록 실패 원인, dry-run 요청 본문 확인용). 개인정보는 저장 전 마스킹."""

    __tablename__ = "api_call_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    target: Mapped[str] = mapped_column(String(30))  # naver | supplier:<code> | claude
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    request: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class OrderStatus(str, enum.Enum):
    PAID = "PAID"
    STOCK_CHECKED = "STOCK_CHECKED"
    PURCHASE_REQUESTED = "PURCHASE_REQUESTED"
    SUPPLIER_CONFIRMED = "SUPPLIER_CONFIRMED"
    SHIPPED = "SHIPPED"
    TRACKING_REGISTERED = "TRACKING_REGISTERED"
    DELIVERED = "DELIVERED"
    # 예외 상태
    AWAITING_APPROVAL = "AWAITING_APPROVAL"  # 관리자 발주 승인 대기
    ON_HOLD = "ON_HOLD"                      # 재고 불일치/한도 초과 등으로 보류
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    RETURN_REQUESTED = "RETURN_REQUESTED"
    RETURNED = "RETURNED"
    EXCHANGE_REQUESTED = "EXCHANGE_REQUESTED"
    FAILED = "FAILED"


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    naver_product_order_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    naver_order_id: Mapped[str] = mapped_column(String(50), index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, native_enum=False, length=30), default=OrderStatus.PAID, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    option_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    unit_price: Mapped[Decimal] = mapped_column(Money)
    total_amount: Mapped[Decimal] = mapped_column(Money)
    # 개인정보: 암호화 저장
    buyer_name_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    buyer_phone_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    address_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    hold_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    claim_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    product: Mapped[Product | None] = relationship()
    supplier: Mapped[Supplier | None] = relationship()


class OrderEvent(Base):
    """주문 상태 변경 감사 로그 (append-only)."""

    __tablename__ = "order_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str] = mapped_column(String(30))
    actor: Mapped[str] = mapped_column(String(255))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PurchaseStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    REQUESTING = "REQUESTING"
    REQUESTED = "REQUESTED"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), unique=True)  # 주문당 발주 1건 = 중복 발주 방지
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    status: Mapped[PurchaseStatus] = mapped_column(
        Enum(PurchaseStatus, native_enum=False, length=20), default=PurchaseStatus.PENDING_APPROVAL, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Money)
    supplier_order_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    carrier_code: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 공급사 택배사 코드
    naver_carrier_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tracking_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    order: Mapped[Order] = relationship()
    supplier: Mapped[Supplier] = relationship()


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[str] = mapped_column(String(10))  # info | warning | error | critical
    category: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(String(500))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class DeadLetter(Base):
    __tablename__ = "dead_letters"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_name: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JobRun(Base):
    __tablename__ = "job_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    job: Mapped[str] = mapped_column(String(100), index=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MockNaverOrder(Base):
    """Mock 네이버 주문함 (NAVER_MODE=mock 일 때만 사용). 실제 네이버 응답 형태를 흉내낸다."""

    __tablename__ = "mock_naver_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_order_id: Mapped[str] = mapped_column(String(50), unique=True)
    order_id: Mapped[str] = mapped_column(String(50))
    origin_product_no: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), default="PAYED")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
