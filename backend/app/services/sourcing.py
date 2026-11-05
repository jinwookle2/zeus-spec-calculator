"""공급사 상품 수집: 정규화, 중복 감지, 품절/단종 반영, 상품코드 매핑."""
from __future__ import annotations

import hashlib
import re
from decimal import Decimal

from sqlalchemy.orm import Session

from app.adapters.base import SupplierItem
from app.adapters.registry import get_adapter
from app.logging_setup import log
from app.models import Supplier, SupplierProduct, SupplierProductStatus


def content_hash(item: SupplierItem) -> str:
    """동일 상품 판별용 해시: 정규화한 상품명 + 옵션명 집합 (공급사/코드와 무관)."""
    name = re.sub(r"[^\w가-힣]", "", item.name).lower()
    opts = sorted(re.sub(r"\s+", "", str(o.get("name", ""))).lower() for o in item.options)
    return hashlib.sha256((name + "|" + ",".join(opts)).encode()).hexdigest()


def sync_supplier(db: Session, supplier: Supplier) -> dict:
    adapter = get_adapter(supplier)
    items = adapter.fetch_products()
    summary = {"supplier": supplier.code, "fetched": len(items), "created": 0, "updated": 0, "sold_out": 0,
               "duplicates": 0, "discontinued": 0}
    existing = {sp.supplier_sku: sp for sp in db.query(SupplierProduct).filter_by(supplier_id=supplier.id)}
    seen = set()
    for item in items:
        seen.add(item.sku)
        h = content_hash(item)
        sp = existing.get(item.sku)
        if sp is None:
            sp = SupplierProduct(supplier_id=supplier.id, supplier_sku=item.sku, content_hash=h, supply_price=item.supply_price)
            db.add(sp)
            summary["created"] += 1
        else:
            summary["updated"] += 1
        sp.name, sp.brand, sp.category_hint = item.name, item.brand, item.category_hint
        sp.supply_price, sp.shipping_fee, sp.stock = Decimal(item.supply_price), Decimal(item.shipping_fee), item.stock
        sp.options, sp.images, sp.attributes, sp.description = item.options, item.images, item.attributes, item.description
        sp.content_hash = h
        db.flush()

        dup = (db.query(SupplierProduct)
               .filter(SupplierProduct.content_hash == h, SupplierProduct.id != sp.id,
                       SupplierProduct.status != SupplierProductStatus.DUPLICATE)
               .order_by(SupplierProduct.id).first())
        if item.discontinued:
            sp.status = SupplierProductStatus.DISCONTINUED
            summary["discontinued"] += 1
        elif dup is not None and dup.id < sp.id:
            sp.status, sp.duplicate_of_id = SupplierProductStatus.DUPLICATE, dup.id
            summary["duplicates"] += 1
        elif item.stock <= 0:
            sp.status = SupplierProductStatus.SOLD_OUT
            summary["sold_out"] += 1
        else:
            sp.status, sp.duplicate_of_id = SupplierProductStatus.ACTIVE, None

    for sku, sp in existing.items():
        if sku not in seen and sp.status != SupplierProductStatus.DISCONTINUED:
            sp.status = SupplierProductStatus.DISCONTINUED
            sp.stock = 0
            summary["discontinued"] += 1
    db.flush()
    log.info("sourcing.synced", **summary)
    return summary


def sync_all_suppliers(db: Session) -> list[dict]:
    return [sync_supplier(db, s) for s in db.query(Supplier).filter_by(active=True).all()]
