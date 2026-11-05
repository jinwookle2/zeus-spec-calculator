from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    Alert, DeadLetter, Order, OrderStatus as S, Product, ProductStatus, PurchaseOrder, PurchaseStatus, Supplier,
    SupplierProduct, utcnow,
)
from app.services import pricing
from app.services.listing import listed_today_count
from app.services.settings_service import get_all_settings

EXCLUDED = (S.CANCELLED, S.RETURNED, S.FAILED)


def dashboard(db: Session) -> dict:
    s = get_all_settings(db)
    prod = dict(db.query(Product.status, func.count()).group_by(Product.status).all())
    orders = dict(db.query(Order.status, func.count()).group_by(Order.status).all())
    return {
        "products": {k.value: v for k, v in prod.items()},
        "orders": {k.value: v for k, v in orders.items()},
        "supplier_products": db.query(func.count(SupplierProduct.id)).scalar(),
        "suppliers": db.query(func.count(Supplier.id)).scalar(),
        "listed_today": listed_today_count(db),
        "daily_listing_limit": s["daily_listing_limit"],
        "awaiting_purchase_approval": orders.get(S.AWAITING_APPROVAL, 0),
        "on_hold": orders.get(S.ON_HOLD, 0),
        "open_alerts": db.query(func.count(Alert.id)).filter_by(acknowledged=False).scalar(),
        "dead_letters": db.query(func.count(DeadLetter.id)).filter_by(resolved=False).scalar(),
        "revenue_30d": revenue(db, 30),
    }


def revenue(db: Session, days: int = 30) -> dict:
    """정산 추정: 매출 - 플랫폼 수수료(설정값) - 광고비(설정값) - 공급사 발주액 - 기타 변동비."""
    s = get_all_settings(db)
    cfg = pricing.PricingConfig.from_settings(s)
    since = utcnow() - timedelta(days=days)
    rows = db.query(Order).filter(Order.created_at >= since, Order.status.notin_(EXCLUDED)).all()
    sales = sum((o.total_amount for o in rows), Decimal(0))
    fees = (sales * cfg.total_fee_rate).quantize(Decimal("1"))
    ads = (sales * cfg.ad_cost_rate).quantize(Decimal("1")) + cfg.ad_cost_per_order * len(rows)
    po_rows = (db.query(PurchaseOrder).join(Order)
               .filter(Order.created_at >= since, Order.status.notin_(EXCLUDED), PurchaseOrder.status != PurchaseStatus.CANCELLED))
    cost = sum((po.amount for po in po_rows), Decimal(0))
    other = cfg.other_variable_cost * len(rows)
    profit = sales - fees - ads - cost - other
    by_day: dict[str, Decimal] = {}
    for o in rows:
        k = o.created_at.date().isoformat()
        by_day[k] = by_day.get(k, Decimal(0)) + o.total_amount
    return {
        "days": days, "orders": len(rows), "sales": str(sales), "platform_fees": str(fees), "ad_cost": str(ads),
        "supplier_cost": str(cost), "other_cost": str(other), "estimated_profit": str(profit),
        "margin_rate": str((profit / sales).quantize(Decimal("0.0001"))) if sales else "0",
        "by_day": {k: str(v) for k, v in sorted(by_day.items())},
        "note": "추정치. 실제 정산은 네이버 정산 내역으로 대사 필요",
    }
