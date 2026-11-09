"""주문 상태 머신 + 감사 로그."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Order, OrderEvent, OrderStatus as S

ALLOWED: dict[S, set[S]] = {
    S.PAID: {S.STOCK_CHECKED, S.ON_HOLD, S.CANCEL_REQUESTED, S.CANCELLED, S.FAILED},
    S.STOCK_CHECKED: {S.PURCHASE_REQUESTED, S.AWAITING_APPROVAL, S.ON_HOLD, S.CANCEL_REQUESTED, S.CANCELLED},
    S.AWAITING_APPROVAL: {S.PURCHASE_REQUESTED, S.ON_HOLD, S.CANCEL_REQUESTED, S.CANCELLED},
    S.ON_HOLD: {S.PAID, S.STOCK_CHECKED, S.AWAITING_APPROVAL, S.CANCEL_REQUESTED, S.CANCELLED, S.FAILED},
    S.PURCHASE_REQUESTED: {S.SUPPLIER_CONFIRMED, S.ON_HOLD, S.FAILED, S.CANCEL_REQUESTED},
    S.SUPPLIER_CONFIRMED: {S.SHIPPED, S.CANCEL_REQUESTED, S.ON_HOLD},
    S.SHIPPED: {S.TRACKING_REGISTERED, S.ON_HOLD, S.RETURN_REQUESTED},
    S.TRACKING_REGISTERED: {S.DELIVERED, S.RETURN_REQUESTED, S.EXCHANGE_REQUESTED},
    S.DELIVERED: {S.RETURN_REQUESTED, S.EXCHANGE_REQUESTED},
    S.CANCEL_REQUESTED: {S.CANCELLED, S.ON_HOLD, S.SUPPLIER_CONFIRMED, S.SHIPPED},
    S.RETURN_REQUESTED: {S.RETURNED, S.DELIVERED},
    S.EXCHANGE_REQUESTED: {S.DELIVERED, S.TRACKING_REGISTERED},
    S.FAILED: {S.ON_HOLD, S.CANCELLED},
    S.CANCELLED: set(),
    S.RETURNED: set(),
}


class InvalidTransition(Exception):
    pass


def transition(db: Session, order: Order, to: S, actor: str, reason: str | None = None) -> Order:
    if order.status == to:
        return order
    if to not in ALLOWED[order.status]:
        raise InvalidTransition(f"{order.naver_product_order_id}: {order.status.value} → {to.value} 불가")
    db.add(OrderEvent(order_id=order.id, from_status=order.status.value, to_status=to.value, actor=actor, reason=reason))
    order.status = to
    if to in (S.ON_HOLD, S.FAILED, S.AWAITING_APPROVAL):
        order.hold_reason = reason
    return order
