from decimal import Decimal as D

from app.services import pricing
from app.services.settings_service import DEFAULTS


def cfg(**kw):
    s = dict(DEFAULTS, **kw)
    return pricing.PricingConfig.from_settings(s)


def test_suggest_price_meets_target_and_min_profit():
    c = cfg()
    r = pricing.suggest_price(6900, 3000, c)
    assert r.ok
    assert r.margin_rate >= D("0.25")
    assert r.expected_profit >= D(3000)
    assert r.sale_price % 100 == 0
    # 한 단위 낮추면 조건 미달 (최소 판매가)
    lower = pricing.evaluate(r.sale_price - 100, 6900, 3000, c)
    assert not lower.ok


def test_profit_formula_explicit():
    c = cfg(platform_fee_rates={"fee": 0.05}, ad_cost_rate=0.02, other_variable_cost=500, customer_shipping_fee=0)
    r = pricing.evaluate(20000, 8000, 3000, c)
    # 20000 - 1000(수수료) - 400(광고) - (8000+3000+500) = 7100
    assert r.expected_profit == D(7100)
    assert r.margin_rate == D("0.3550")
    assert r.ok


def test_min_profit_dominates_for_cheap_items():
    c = cfg(min_profit_krw=5000)
    r = pricing.suggest_price(1000, 0, c)
    assert r.expected_profit >= 5000 and r.ok
    assert r.margin_rate > D("0.25")


def test_customer_shipping_fee_counts_as_revenue():
    free = pricing.suggest_price(10000, 3000, cfg(customer_shipping_fee=0))
    paid = pricing.suggest_price(10000, 3000, cfg(customer_shipping_fee=3000))
    assert paid.sale_price < free.sale_price
    assert paid.ok


def test_infeasible_configuration_blocks():
    r = pricing.suggest_price(5000, 0, cfg(target_margin_rate=0.7, ad_cost_rate=0.3))
    assert not r.feasible and not r.ok
    assert "INFEASIBLE" in r.reasons[0]


def test_below_target_reasons():
    r = pricing.evaluate(9000, 6900, 3000, cfg())
    assert not r.ok
    assert any(x.startswith("MARGIN_BELOW_TARGET") for x in r.reasons)
    assert any(x.startswith("PROFIT_BELOW_MIN") for x in r.reasons)
