"""공급사 Adapter 인터페이스.

공급사마다 인증/상품/발주 방식이 다르므로, 각 공급사는 이 인터페이스를 구현한다.
실제 연동 명세(계약서, API 문서)가 없는 공급사는 MockSupplierAdapter 를 사용한다.
허가받지 않은 크롤링, 로그인 우회, CAPTCHA 우회는 구현하지 않는다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal


class AdapterError(Exception):
    """재시도 가능한 일시적 오류."""


class PurchaseNotSupported(Exception):
    """발주 API 미지원 → 관리자 수동 발주."""


@dataclass
class SupplierItem:
    sku: str
    name: str
    supply_price: Decimal
    shipping_fee: Decimal
    stock: int
    brand: str | None = None
    category_hint: str | None = None
    options: list[dict] = field(default_factory=list)  # [{"name": "색상:블랙/사이즈:M", "sku": "...", "stock": 3, "extra_price": 0}]
    images: list[str] = field(default_factory=list)
    attributes: dict = field(default_factory=dict)     # manufacturer, origin, material, certifications, notice, retail_price
    description: str | None = None
    discontinued: bool = False


@dataclass
class StockInfo:
    sku: str
    stock: int
    supply_price: Decimal
    available: bool


@dataclass
class PurchaseRequest:
    idempotency_key: str
    sku: str
    option_sku: str | None
    quantity: int
    recipient: dict  # name/phone/address — 승인 범위 밖이면 마스킹된 값만 전달
    memo: str | None = None
    attempt: int = 1  # 동일 멱등키로 몇 번째 시도인지


@dataclass
class PurchaseResult:
    supplier_order_no: str
    status: str  # REQUESTED | CONFIRMED
    raw: dict = field(default_factory=dict)


@dataclass
class ShipmentInfo:
    status: str  # PENDING | CONFIRMED | SHIPPED | DELIVERED | CANCELLED
    carrier_code: str | None = None
    tracking_no: str | None = None


class SupplierAdapter(ABC):
    #: 실제 외부 시스템에 영향을 주는 Adapter 인지 (Mock/CSV 는 False)
    is_live: bool = False
    #: 발주 API 지원 여부
    supports_purchase: bool = False

    def __init__(self, supplier_code: str, config: dict | None = None):
        self.code = supplier_code
        self.config = config or {}

    @abstractmethod
    def fetch_products(self) -> list[SupplierItem]: ...

    @abstractmethod
    def get_stock(self, sku: str) -> StockInfo: ...

    def place_order(self, req: PurchaseRequest) -> PurchaseResult:
        raise PurchaseNotSupported(f"{self.code}: 발주 API 미지원")

    def get_shipment(self, supplier_order_no: str) -> ShipmentInfo:
        raise PurchaseNotSupported(f"{self.code}: 배송 조회 API 미지원")

    def cancel_order(self, supplier_order_no: str) -> bool:
        raise PurchaseNotSupported(f"{self.code}: 발주 취소 API 미지원")

    def request_return(self, supplier_order_no: str, reason: str | None = None) -> str:
        """공급사 반품 접수. 반환: 공급사 반품 접수번호."""
        raise PurchaseNotSupported(f"{self.code}: 반품 접수 API 미지원")
