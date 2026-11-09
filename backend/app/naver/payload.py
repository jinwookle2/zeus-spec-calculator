"""네이버 (v2) 상품 등록 요청 본문 생성.

구조 근거: 공식 스펙의 POST /v2/products (originProduct + smartstoreChannelProduct).
상품군별 고시정보(productInfoProvidedNotice) 세부 필드와 원산지 코드는
운영 전 /v1/products-for-provided-notice, /v1/product-origin-areas 로 확인해야 한다.
"""
from __future__ import annotations

from app.models import Product


def build_product_payload(p: Product, image_urls: list[str], origin_area_code: str | None,
                          customer_shipping_fee: int, return_fee: int = 3000) -> dict:
    sp = p.supplier_product
    attrs = sp.attributes or {}
    rep, *extra = image_urls
    option_info = None
    if p.options_normalized:
        group_names = sorted({k for o in p.options_normalized for k in o["values"]})[:3]
        option_info = {
            "optionCombinationSortType": "CREATE",
            "optionCombinationGroupNames": {f"optionGroupName{i + 1}": g for i, g in enumerate(group_names)},
            "optionCombinations": [
                {
                    **{f"optionName{i + 1}": o["values"].get(g, "") for i, g in enumerate(group_names)},
                    "stockQuantity": o["stock"],
                    "price": int(o.get("extra_price", 0)),
                    "sellerManagerCode": o["sku"],
                    "usable": True,
                }
                for o in p.options_normalized
            ],
        }
    detail_attribute = {
        "naverShoppingSearchInfo": {"manufacturerName": attrs.get("manufacturer"), "brandName": sp.brand or None},
        "originAreaInfo": {"originAreaCode": origin_area_code, "content": attrs.get("origin")},
        "afterServiceInfo": {"afterServiceTelephoneNumber": attrs.get("as_phone", ""),
                             "afterServiceGuideContent": attrs.get("as_guide", "판매자 고객센터로 문의")},
        "minorPurchasable": True,
        "seoInfo": {"sellerTags": [{"text": t} for t in p.tags[:10]]},
        "sellerCodeInfo": {"sellerManagementCode": p.listing_key},
        "productInfoProvidedNotice": p.notice or {},
    }
    if option_info:
        detail_attribute["optionInfo"] = option_info
    return {
        "originProduct": {
            "statusType": "SALE",
            "saleType": "NEW",
            "leafCategoryId": p.category_id,
            "name": p.title,
            "detailContent": p.detail_html,
            "images": {"representativeImage": {"url": rep}, "optionalImages": [{"url": u} for u in extra[:9]]},
            "salePrice": int(p.sale_price),
            "stockQuantity": p.stock,
            "deliveryInfo": {
                "deliveryType": "DELIVERY",
                "deliveryAttributeType": "NORMAL",
                "deliveryFee": (
                    {"deliveryFeeType": "FREE"} if customer_shipping_fee <= 0
                    else {"deliveryFeeType": "PAID", "baseFee": customer_shipping_fee}
                ),
                "claimDeliveryInfo": {"returnDeliveryFee": return_fee, "exchangeDeliveryFee": return_fee * 2},
            },
            "detailAttribute": detail_attribute,
        },
        "smartstoreChannelProduct": {
            "naverShoppingRegistration": True,
            "channelProductDisplayStatusType": "ON",
        },
    }
