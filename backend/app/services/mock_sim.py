"""Mock 네이버 주문 시뮬레이터 (NAVER_MODE=mock 전용)."""
from __future__ import annotations

import random

from sqlalchemy.orm import Session

from app.models import MockNaverOrder, Product, ProductStatus, utcnow

NAMES = ["김민준", "이서연", "박지호", "최수아", "정예준"]
ADDRS = ["서울특별시 강남구 테헤란로 123 4층", "부산광역시 해운대구 센텀중앙로 55 101호", "대전광역시 유성구 대학로 99"]


def simulate_order(db: Session, product: Product, quantity: int = 1, option_label: str | None = None,
                   seed: int | None = None) -> MockNaverOrder:
    if product.status not in (ProductStatus.LISTED, ProductStatus.SOLD_OUT):
        raise ValueError("등록(LISTED) 상품만 주문 시뮬레이션 가능")
    rnd = random.Random(seed)
    n = db.query(MockNaverOrder).count() + 1
    po_id = f"2026{n:010d}"
    option_label = option_label or (product.options_normalized[0]["label"] if product.options_normalized else None)
    payload = {
        "order": {"orderId": f"ORD{n:08d}", "ordererName": rnd.choice(NAMES), "paymentDate": utcnow().isoformat()},
        "productOrder": {
            "productOrderId": po_id, "productOrderStatus": "PAYED", "sellerProductCode": product.listing_key,
            "originalProductId": product.naver_origin_product_no, "productId": product.naver_channel_product_no,
            "quantity": quantity,
            "unitPrice": int(product.sale_price), "totalPaymentAmount": int(product.sale_price) * quantity,
            "productOption": option_label,
            "shippingAddress": {"name": rnd.choice(NAMES), "tel1": f"010-{rnd.randint(1000, 9999)}-{rnd.randint(1000, 9999)}",
                                "baseAddress": rnd.choice(ADDRS), "detailedAddress": "", "zipCode": "06234"},
        },
    }
    row = MockNaverOrder(product_order_id=po_id, order_id=payload["order"]["orderId"],
                         origin_product_no=product.naver_origin_product_no or "", status="PAYED", payload=payload)
    db.add(row)
    db.flush()
    return row


def set_mock_status(db: Session, product_order_id: str, status: str, claim_type: str | None = None) -> MockNaverOrder:
    row = db.query(MockNaverOrder).filter_by(product_order_id=product_order_id).one()
    row.status = status
    po = dict(row.payload["productOrder"])
    po["claimType"] = claim_type
    row.payload = {**row.payload, "productOrder": po}
    row.changed_at = utcnow()
    db.flush()
    return row
