"""가격/마진 계산.

정의 (모두 원 단위, Decimal):
  매출 R        = 판매가 P + 고객부담 배송비 Sc
  플랫폼 수수료 = R × Σ(수수료율)
  광고비        = P × 광고비율 + 주문당 광고비
  원가          = 공급가 + 공급사 배송비 + 기타 변동비
  예상 이익     = R − 수수료 − 광고비 − 원가
  마진율        = 예상 이익 / R
판매가는 (목표 마진율, 최소 이익금) 두 조건을 모두 만족하는 최소가를 반올림 단위로 올림한다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from typing import Any

D = Decimal


def _d(v: Any) -> Decimal:
    return v if isinstance(v, Decimal) else D(str(v))


@dataclass
class PricingConfig:
    target_margin_rate: Decimal
    min_profit: Decimal
    fee_rates: dict[str, Decimal]
    ad_cost_rate: Decimal
    ad_cost_per_order: Decimal = D(0)
    other_variable_cost: Decimal = D(0)
    customer_shipping_fee: Decimal = D(0)
    rounding_unit: Decimal = D(100)

    @classmethod
    def from_settings(cls, s: dict[str, Any]) -> "PricingConfig":
        return cls(
            target_margin_rate=_d(s["target_margin_rate"]),
            min_profit=_d(s["min_profit_krw"]),
            fee_rates={k: _d(v) for k, v in s["platform_fee_rates"].items()},
            ad_cost_rate=_d(s["ad_cost_rate"]),
            ad_cost_per_order=_d(s["ad_cost_per_order"]),
            other_variable_cost=_d(s["other_variable_cost"]),
            customer_shipping_fee=_d(s["customer_shipping_fee"]),
            rounding_unit=_d(s["price_rounding_unit"]),
        )

    @property
    def total_fee_rate(self) -> Decimal:
        return sum(self.fee_rates.values(), D(0))


@dataclass
class PriceResult:
    sale_price: Decimal
    revenue: Decimal
    platform_fee: Decimal
    ad_cost: Decimal
    supply_cost: Decimal
    expected_profit: Decimal
    margin_rate: Decimal
    meets_target: bool
    meets_min_profit: bool
    feasible: bool = True
    reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.feasible and self.meets_target and self.meets_min_profit

    def breakdown(self) -> dict[str, str]:
        return {k: str(v) for k, v in asdict(self).items() if isinstance(v, Decimal)}


def evaluate(sale_price: Any, supply_price: Any, supplier_shipping: Any, cfg: PricingConfig) -> PriceResult:
    p = _d(sale_price)
    revenue = p + cfg.customer_shipping_fee
    fee = (revenue * cfg.total_fee_rate).quantize(D("1"), ROUND_HALF_UP)
    ad = (p * cfg.ad_cost_rate + cfg.ad_cost_per_order).quantize(D("1"), ROUND_HALF_UP)
    cost = _d(supply_price) + _d(supplier_shipping) + cfg.other_variable_cost
    profit = revenue - fee - ad - cost
    margin = (profit / revenue).quantize(D("0.0001"), ROUND_HALF_UP) if revenue > 0 else D(0)
    reasons = []
    meets_target = margin >= cfg.target_margin_rate
    meets_min = profit >= cfg.min_profit
    if not meets_target:
        reasons.append(f"MARGIN_BELOW_TARGET: {margin} < {cfg.target_margin_rate}")
    if not meets_min:
        reasons.append(f"PROFIT_BELOW_MIN: {profit} < {cfg.min_profit}")
    return PriceResult(p, revenue, fee, ad, cost, profit, margin, meets_target, meets_min, True, reasons)


def suggest_price(supply_price: Any, supplier_shipping: Any, cfg: PricingConfig) -> PriceResult:
    f, a, t = cfg.total_fee_rate, cfg.ad_cost_rate, cfg.target_margin_rate
    sc = cfg.customer_shipping_fee
    k = _d(supply_price) + _d(supplier_shipping) + cfg.other_variable_cost + cfg.ad_cost_per_order

    denom_target = 1 - f - a - t
    denom_min = 1 - f - a
    if denom_target <= 0 or denom_min <= 0:
        return PriceResult(D(0), D(0), D(0), D(0), k, D(0), D(0), False, False, False,
                           ["INFEASIBLE: 수수료+광고비+목표마진 합이 100% 이상"])
    p_target = (k - sc * (1 - f - t)) / denom_target
    p_min = (k + cfg.min_profit - sc * (1 - f)) / denom_min
    raw = max(p_target, p_min, D(0))
    unit = cfg.rounding_unit if cfg.rounding_unit > 0 else D(1)
    price = (raw / unit).to_integral_value(ROUND_CEILING) * unit
    # 반올림 오차로 조건 미달 시 한 단위씩 올림
    for _ in range(5):
        res = evaluate(price, supply_price, supplier_shipping, cfg)
        if res.ok:
            return res
        price += unit
    return evaluate(price, supply_price, supplier_shipping, cfg)
