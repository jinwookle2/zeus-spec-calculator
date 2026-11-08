"""가공 → 검증 → 가격 → 승인 → 스마트스토어 등록 → 재고/가격 동기화."""
from __future__ import annotations

from datetime import datetime, time, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.adapters.registry import get_adapter
from app.config import get_settings
from app.logging_setup import log
from app.models import Product, ProductStatus, Supplier, SupplierProduct, SupplierProductStatus, utcnow
from app.naver.client import NaverApiError, NaverClient
from app.naver.payload import build_product_payload
from app.services import pricing
from app.services.ai_processor import get_processor
from app.services.alerts import audit, raise_alert
from app.services.categories import load_category_map
from app.services.compliance import check_product
from app.services.settings_service import get_all_settings


def listing_key(supplier: Supplier, sku: str) -> str:
    """상품별 고유 키 = 공급사코드:공급사상품코드. 네이버 sellerManagementCode 로도 사용 → 중복 등록 방지."""
    return f"{supplier.code}:{sku}"


def _price_check(sp: SupplierProduct, s: dict, sale_price: Decimal | None = None) -> tuple[pricing.PriceResult, list[str]]:
    cfg = pricing.PricingConfig.from_settings(s)
    res = (pricing.evaluate(sale_price, sp.supply_price, sp.shipping_fee, cfg) if sale_price is not None
           else pricing.suggest_price(sp.supply_price, sp.shipping_fee, cfg))
    blocks = list(res.reasons) if not res.ok else []
    retail = (sp.attributes or {}).get("retail_price")
    if retail and res.sale_price > Decimal(str(retail)):
        blocks.append(f"PRICE_ABOVE_MARKET: 필요 판매가 {res.sale_price} > 시장가 {retail} (최소 이익 조건 충족 불가)")
    return res, blocks


def process_supplier_product(db: Session, sp: SupplierProduct, settings: dict | None = None,
                             categories: dict[str, str] | None = None) -> Product:
    s = settings or get_all_settings(db)
    categories = categories if categories is not None else load_category_map(db)
    supplier = sp.supplier
    product = db.query(Product).filter_by(supplier_product_id=sp.id).one_or_none()
    if product and product.status in (ProductStatus.LISTED, ProductStatus.APPROVED):
        return product  # 등록/승인된 상품은 재가공하지 않음 (가격/재고 동기화는 별도)

    content = get_processor().process(sp, categories=categories)
    comp = check_product(sp, supplier, s)
    price, price_blocks = _price_check(sp, s)
    blocks = comp.blocks + price_blocks
    warnings = comp.warnings + content.warnings
    if not content.category_id:
        blocks.append("CATEGORY_REQUIRED")

    if product is None:
        product = Product(supplier_product_id=sp.id, supplier_id=supplier.id,
                          listing_key=listing_key(supplier, sp.supplier_sku))
        db.add(product)
    product.title, product.category_id, product.category_name = content.title, content.category_id, content.category_name
    product.tags, product.detail_html = content.tags, content.detail_html
    product.options_normalized, product.notice, product.ai_source = content.options, content.notice, content.source
    product.sale_price, product.expected_profit, product.margin_rate = price.sale_price, price.expected_profit, price.margin_rate
    product.cost_breakdown = price.breakdown()
    product.stock = sp.stock
    product.block_reasons, product.warnings = blocks, warnings

    auto = (s["auto_listing_enabled"] and supplier.verified and supplier.auto_listing_allowed and not warnings)
    if blocks:
        product.status = ProductStatus.BLOCKED
    elif auto:
        product.status, product.approved_by = ProductStatus.APPROVED, "system:auto"
    else:
        product.status = ProductStatus.PENDING_APPROVAL
    db.flush()
    return product


def process_new_candidates(db: Session, limit: int = 200) -> dict:
    s = get_all_settings(db)
    q = (db.query(SupplierProduct)
         .outerjoin(Product, Product.supplier_product_id == SupplierProduct.id)
         .join(Supplier, Supplier.id == SupplierProduct.supplier_id)
         .filter(Product.id.is_(None), SupplierProduct.status == SupplierProductStatus.ACTIVE, Supplier.active.is_(True))
         .limit(limit))
    counts: dict[str, int] = {}
    categories = load_category_map(db)
    for sp in q.all():
        p = process_supplier_product(db, sp, s, categories)
        counts[p.status.value] = counts.get(p.status.value, 0) + 1
    return counts


def approve_product(db: Session, product: Product, actor: str, sale_price: Decimal | None = None) -> Product:
    if product.status not in (ProductStatus.PENDING_APPROVAL, ProductStatus.FAILED, ProductStatus.BLOCKED):
        raise ValueError(f"승인 불가 상태: {product.status.value}")
    s = get_all_settings(db)
    sp = product.supplier_product
    if sale_price is not None:
        res, price_blocks = _price_check(sp, s, Decimal(sale_price))
        product.sale_price, product.expected_profit, product.margin_rate = res.sale_price, res.expected_profit, res.margin_rate
        product.cost_breakdown = res.breakdown()
        non_price = [b for b in product.block_reasons if not b.startswith(("MARGIN_", "PROFIT_", "PRICE_ABOVE"))]
        product.block_reasons = non_price + price_blocks
    if product.block_reasons:
        raise ValueError(f"차단 사유가 있어 승인할 수 없습니다: {product.block_reasons}")
    product.status, product.approved_by, product.last_error = ProductStatus.APPROVED, actor, None
    audit(db, actor, "product.approve", "product", product.id, sale_price=str(product.sale_price))
    return product


def listed_today_count(db: Session) -> int:
    start = datetime.combine(utcnow().date(), time.min, tzinfo=timezone.utc)
    return db.query(func.count(Product.id)).filter(Product.listed_at >= start).scalar() or 0


def publish_approved(db: Session, naver: NaverClient) -> dict:
    s = get_all_settings(db)
    remaining = max(0, int(s["daily_listing_limit"]) - listed_today_count(db))
    summary = {"listed": 0, "failed": 0, "skipped_limit": 0, "remaining_before": remaining}
    approved = db.query(Product).filter_by(status=ProductStatus.APPROVED).order_by(Product.id).all()
    origin_codes = s.get("origin_area_codes") or {}
    for p in approved:
        if summary["listed"] >= remaining:
            summary["skipped_limit"] += 1
            continue
        if p.naver_origin_product_no:  # 이미 등록된 상품 → 중복 등록 방지
            p.status = ProductStatus.LISTED
            continue
        origin = (p.supplier_product.attributes or {}).get("origin")
        if naver.mode == "live" and not origin_codes.get(origin):
            p.status, p.last_error = ProductStatus.FAILED, f"원산지 코드 매핑 필요: '{origin}' (설정 origin_area_codes)"
            summary["failed"] += 1
            continue
        try:
            restricted = naver.check_restricted_tags(list(p.tags))
        except NaverApiError as e:
            restricted = set()
            p.warnings = list(p.warnings) + [f"RESTRICTED_TAG_CHECK_FAILED: {e}"]
        if restricted:
            p.tags = [t for t in p.tags if t not in restricted]
            p.warnings = list(p.warnings) + [f"RESTRICTED_TAGS_REMOVED: {sorted(restricted)}"]
        try:
            images = naver.upload_images(p.supplier_product.images[:10])
            payload = build_product_payload(p, images, origin_codes.get(origin),
                                            int(s["customer_shipping_fee"]))
            res = naver.create_product(payload, p.listing_key)
            p.naver_origin_product_no = str(res.get("originProductNo") or res.get("id"))
            p.naver_channel_product_no = str(res.get("smartstoreChannelProductNo") or "") or None
            p.dry_run_listed = bool(res.get("dryRun"))
            p.status, p.listed_at, p.last_error = ProductStatus.LISTED, utcnow(), None
            summary["listed"] += 1
        except NaverApiError as e:
            p.status, p.last_error = ProductStatus.FAILED, f"{e} body={e.body}"
            summary["failed"] += 1
            raise_alert(db, "warning", "listing", f"상품 등록 실패: {p.listing_key}", {"error": str(e), "body": e.body})
        db.flush()
    db.flush()
    log.info("listing.published", **summary)
    return summary


def sync_inventory(db: Session, naver: NaverClient) -> dict:
    """등록 상품의 공급사 재고/공급가를 확인해 네이버 재고·판매가·판매상태를 맞춘다."""
    s = get_all_settings(db)
    cfg = pricing.PricingConfig.from_settings(s)
    summary = {"checked": 0, "stock_updated": 0, "sold_out": 0, "repriced": 0, "suspended": 0, "restocked": 0}
    products = db.query(Product).filter(Product.status.in_([ProductStatus.LISTED, ProductStatus.SOLD_OUT])).all()
    adapters: dict[int, object] = {}
    for p in products:
        if not p.naver_origin_product_no:
            continue
        adapter = adapters.setdefault(p.supplier_id, get_adapter(p.supplier))
        info = adapter.get_stock(p.supplier_product.supplier_sku)
        summary["checked"] += 1
        sp = p.supplier_product
        sp.stock = info.stock
        if not info.available or info.stock <= 0:
            if p.status != ProductStatus.SOLD_OUT:
                naver.change_status(p.naver_origin_product_no, "OUTOFSTOCK", 0)
                p.status, p.stock = ProductStatus.SOLD_OUT, 0
                summary["sold_out"] += 1
            continue
        if info.supply_price != sp.supply_price:
            sp.supply_price = info.supply_price
            res = pricing.evaluate(p.sale_price, sp.supply_price, sp.shipping_fee, cfg)
            if not res.ok:
                new = pricing.suggest_price(sp.supply_price, sp.shipping_fee, cfg)
                retail = (sp.attributes or {}).get("retail_price")
                if retail and new.sale_price > Decimal(str(retail)):
                    naver.change_status(p.naver_origin_product_no, "SUSPENSION")
                    p.status = ProductStatus.SUSPENDED
                    p.last_error = f"공급가 상승으로 최소 이익 미달 → 판매중지 ({info.supply_price})"
                    summary["suspended"] += 1
                    raise_alert(db, "warning", "pricing", f"판매중지: {p.listing_key} 공급가 상승", {"supply": str(info.supply_price)})
                    continue
                naver.update_price_stock(p.naver_origin_product_no, sale_price=int(new.sale_price))
                p.sale_price, p.expected_profit, p.margin_rate = new.sale_price, new.expected_profit, new.margin_rate
                p.cost_breakdown = new.breakdown()
                summary["repriced"] += 1
        if p.status == ProductStatus.SOLD_OUT:
            naver.change_status(p.naver_origin_product_no, "SALE", info.stock)
            p.status = ProductStatus.LISTED
            summary["restocked"] += 1
        if info.stock != p.stock:
            naver.update_price_stock(p.naver_origin_product_no, stock=info.stock)
            p.stock = info.stock
            summary["stock_updated"] += 1
    db.flush()
    return summary


def suspend_product(db: Session, naver: NaverClient, product: Product, actor: str) -> Product:
    if product.naver_origin_product_no:
        naver.change_status(product.naver_origin_product_no, "SUSPENSION")
    product.status = ProductStatus.SUSPENDED
    audit(db, actor, "product.suspend", "product", product.id)
    return product


def live_listing_enabled() -> bool:
    s = get_settings()
    return s.naver_mode == "live" and s.allow_public_listing
