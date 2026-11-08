"""네이버 정산 대사: 건별 정산 내역을 받아 주문과 연결하고, 실제 수수료와 설정 수수료율 추정치를 비교한다."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Order, Settlement, utcnow
from app.naver.client import NaverClient
from app.services import pricing
from app.services.alerts import raise_alert
from app.services.settings_service import get_all_settings


def _d(v) -> Decimal:
    return Decimal(str(v or 0))


def reconcile_settlements(db: Session, naver: NaverClient, days: int | None = None) -> dict:
    s = get_all_settings(db)
    days = days or int(s["settlement_lookback_days"])
    cfg = pricing.PricingConfig.from_settings(s)
    tol = _d(s["settlement_fee_tolerance_krw"])
    summary = {"days": days, "fetched": 0, "created": 0, "matched": 0, "mismatch": 0, "new_mismatch": 0}
    today = utcnow().date()
    for i in range(days):
        day = (today - timedelta(days=i)).isoformat()
        page, total = 1, 1
        while page <= total:
            elements, total = naver.get_settlements(day, page)
            for e in elements:
                summary["fetched"] += 1
                _upsert(db, e, cfg, tol, summary)
            page += 1
    db.flush()
    if summary["new_mismatch"]:
        raise_alert(db, "warning", "settlement",
                    f"정산 수수료 불일치 {summary['new_mismatch']}건: 설정 수수료율(platform_fee_rates) 확인 필요",
                    {"tolerance_krw": str(tol)})
    return summary


def _upsert(db: Session, e: dict, cfg: pricing.PricingConfig, tol: Decimal, summary: dict) -> None:
    po_id, stype = str(e["productOrderId"]), e.get("settleType") or "UNKNOWN"
    row = db.query(Settlement).filter_by(product_order_id=po_id, settle_type=stype).one_or_none()
    if row is None:
        row = Settlement(product_order_id=po_id, settle_type=stype)
        db.add(row)
        summary["created"] += 1
    was_mismatch = row.mismatch
    pay = _d(e.get("paySettleAmount"))
    # 수수료 금액은 부호(차감 표기)와 무관하게 절댓값 합으로 비교
    commission = sum((abs(_d(e.get(k))) for k in
                      ("totalPayCommissionAmount", "sellingInterlockCommissionAmount", "freeInstallmentCommissionAmount")),
                     Decimal(0))
    row.naver_order_id = e.get("orderId")
    row.pay_settle_amount, row.commission_amount = pay, commission
    row.benefit_settle_amount, row.settle_expect_amount = _d(e.get("benefitSettleAmount")), _d(e.get("settleExpectAmount"))
    row.settle_basis_date, row.settle_expect_date = e.get("settleBasisDate"), e.get("settleExpectDate")
    row.settle_complete_date, row.raw = e.get("settleCompleteDate"), e
    order = db.query(Order).filter_by(naver_product_order_id=po_id).one_or_none()
    row.order_id = order.id if order else None
    if order:
        summary["matched"] += 1
    expected = (abs(pay) * cfg.total_fee_rate).quantize(Decimal("1"))
    row.expected_commission, row.commission_diff = expected, commission - expected
    limit = max(tol, (abs(pay) * Decimal("0.005")).quantize(Decimal("1")))
    row.mismatch = stype == "NORMAL_SETTLE_ORIGINAL" and abs(row.commission_diff) > limit
    if row.mismatch:
        summary["mismatch"] += 1
        if not was_mismatch:
            summary["new_mismatch"] += 1
