"""Mock 공급사. 실제 공급사 명세 없이 전체 워크플로를 검증하기 위한 결정적 데이터.

supplier.config 로 동작을 조정할 수 있다 (테스트/시뮬레이션용):
  stock_overrides: {sku: int}          재고 변경 (주문 시 재고 불일치 시뮬레이션)
  price_overrides: {sku: number}       공급가 변경
  prefix / name_suffix                 상품코드 접두어 / 상품명 접미어
  fail_purchase_times: int             발주 요청 시 N회 실패 후 성공 (재시도 검증)
"""
from __future__ import annotations

import hashlib
from decimal import Decimal

from app.adapters.base import (
    AdapterError,
    PurchaseRequest,
    PurchaseResult,
    ShipmentInfo,
    StockInfo,
    SupplierAdapter,
    SupplierItem,
)

IMG = "https://picsum.photos/seed/{seed}/800/800"

_BASE_NOTICE = {"type": "ETC", "품명": "", "모델명": "", "제조자": "", "제조국": "", "A/S 책임자와 전화번호": "공급사 고객센터"}


def _item(sku, name, price, ship, stock, *, brand=None, cat=None, options=None, origin="중국", maker="(주)목업제조",
          material=None, retail=None, desc=None, discontinued=False, notice=True):
    attrs = {"manufacturer": maker, "origin": origin}
    if material:
        attrs["material"] = material
    if retail:
        attrs["retail_price"] = retail
    if notice:
        n = dict(_BASE_NOTICE, 품명=name, 제조자=maker, 제조국=origin)
        attrs["notice"] = n
    return SupplierItem(
        sku=sku, name=name, supply_price=Decimal(price), shipping_fee=Decimal(ship), stock=stock, brand=brand,
        category_hint=cat, options=options or [], images=[IMG.format(seed=sku), IMG.format(seed=sku + "-2")],
        attributes=attrs, description=desc, discontinued=discontinued,
    )


def mock_catalog(prefix: str, name_suffix: str = "") -> list[SupplierItem]:
    p = prefix.upper()
    items = [
        _item(f"{p}-1001", "스테인리스 진공 텀블러 500ml", 6900, 3000, 120, cat="주방용품>보온/보냉용품>텀블러",
              options=[{"name": "색상:블랙", "sku": f"{p}-1001-BK", "stock": 60, "extra_price": 0},
                       {"name": "색상:화이트", "sku": f"{p}-1001-WH", "stock": 60, "extra_price": 0}],
              material="스테인리스스틸 304", retail=24900, desc="이중 진공 구조 텀블러"),
        _item(f"{p}-1002", "접이식 실리콘 수납 바구니 3종 세트", 5200, 3000, 80, cat="생활용품>수납/정리>바구니",
              material="실리콘", retail=19800),
        _item(f"{p}-1003", "LED 무드등 원목 스탠드", 12800, 3500, 35, cat="가구/인테리어>조명>스탠드",
              options=[{"name": "색온도:웜화이트", "sku": f"{p}-1003-W", "stock": 20, "extra_price": 0},
                       {"name": "색온도:쿨화이트", "sku": f"{p}-1003-C", "stock": 15, "extra_price": 1000}],
              retail=39000),
        _item(f"{p}-1004", "반려동물 자동 급수기 2L", 15500, 3500, 40, cat="반려동물>급식/급수용품>급수기", retail=45000),
        _item(f"{p}-1005", "차량용 핸드폰 거치대 송풍구형", 3100, 3000, 200, cat="자동차용품>차량용 거치대", retail=12900),
        _item(f"{p}-1006", "캠핑 접이식 의자 경량", 18900, 4000, 25, cat="스포츠/레저>캠핑>캠핑의자", retail=49000),
        # ---- 검증 시나리오 ----
        _item(f"{p}-2001", "나이키 에어 스타일 운동화", 25000, 3000, 50, brand="나이키", cat="패션잡화>운동화"),  # 브랜드 권한 없음
        _item(f"{p}-2002", "미러급 명품 스타일 카드지갑", 8000, 3000, 30, cat="패션잡화>지갑"),  # 금지 키워드
        _item(f"{p}-2003", "무선 블루투스 이어폰 화이트", 9900, 3000, 0, cat="디지털/가전>음향가전>이어폰"),  # 품절
        _item(f"{p}-2004", "프리미엄 원목 도마 대형", 21000, 3500, 15, cat="주방용품>조리도구>도마", retail=24000),  # 시장가 대비 마진 불가
        _item(f"{p}-2005", "스테인리스 진공 텀블러 500ml", 6900, 3000, 120, cat="주방용품>보온/보냉용품>텀블러",
              options=[{"name": "색상:블랙", "sku": f"{p}-2005-BK", "stock": 60, "extra_price": 0},
                       {"name": "색상:화이트", "sku": f"{p}-2005-WH", "stock": 60, "extra_price": 0}],
              material="스테인리스스틸 304", retail=24900, desc="이중 진공 구조 텀블러"),  # 1001과 중복
        _item(f"{p}-2006", "천연 아로마 디퓨저 200ml", 7400, 3000, 60, cat="생활용품>방향제>디퓨저",
              origin="", notice=False),  # 고시정보 누락
        _item(f"{p}-2007", "단종 예정 전기포트", 11000, 3000, 10, cat="디지털/가전>주방가전>전기포트", discontinued=True),
    ]
    if name_suffix:  # 공급사별로 다른 상품군 흉내 (미설정 시 공급사 간 중복 감지 시나리오)
        for it in items:
            it.name = f"{it.name} {name_suffix}"
            if it.attributes.get("notice"):
                it.attributes["notice"]["품명"] = it.name
    return items


class MockSupplierAdapter(SupplierAdapter):
    is_live = False
    supports_purchase = True

    def _catalog(self) -> dict[str, SupplierItem]:
        items = {i.sku: i for i in mock_catalog(self.config.get("prefix", self.code), self.config.get("name_suffix", ""))}
        for sku, stock in (self.config.get("stock_overrides") or {}).items():
            if sku in items:
                items[sku].stock = int(stock)
        for sku, price in (self.config.get("price_overrides") or {}).items():
            if sku in items:
                items[sku].supply_price = Decimal(str(price))
        return items

    def fetch_products(self) -> list[SupplierItem]:
        return list(self._catalog().values())

    def get_stock(self, sku: str) -> StockInfo:
        item = self._catalog().get(sku)
        if item is None:
            return StockInfo(sku=sku, stock=0, supply_price=Decimal(0), available=False)
        return StockInfo(sku=sku, stock=item.stock, supply_price=item.supply_price,
                         available=item.stock > 0 and not item.discontinued)

    def place_order(self, req: PurchaseRequest) -> PurchaseResult:
        fail_times = int(self.config.get("fail_purchase_times", 0))
        if req.attempt <= fail_times:
            raise AdapterError("mock: 공급사 일시 오류 (503)")
        # 같은 멱등키 → 같은 발주번호 (공급사 측 중복 발주 방지 시뮬레이션)
        no = "MOCK-" + hashlib.sha1(req.idempotency_key.encode()).hexdigest()[:10].upper()
        return PurchaseResult(supplier_order_no=no, status="CONFIRMED", raw={"mock": True})

    def get_shipment(self, supplier_order_no: str) -> ShipmentInfo:
        tracking = str(int(hashlib.sha1(supplier_order_no.encode()).hexdigest()[:10], 16))[:12].rjust(12, "0")
        return ShipmentInfo(status="SHIPPED", carrier_code="CJ", tracking_no=tracking)

    def cancel_order(self, supplier_order_no: str) -> bool:
        return True

    def request_return(self, supplier_order_no: str, reason: str | None = None) -> str:
        return "RET-" + hashlib.sha1(supplier_order_no.encode()).hexdigest()[:8].upper()
