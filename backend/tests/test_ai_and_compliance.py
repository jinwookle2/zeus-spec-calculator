from types import SimpleNamespace

from app.adapters.mock_supplier import mock_catalog
from app.models import Supplier, SupplierProduct
from app.services.ai_processor import (
    ClaudeCopy, ClaudeProcessor, RuleBasedProcessor, clean_title, find_unsupported_claims, normalize_options,
)
from app.services.compliance import check_product
from app.services.settings_service import DEFAULTS


def _sp(item, supplier):
    sp = SupplierProduct(supplier_sku=item.sku, name=item.name, brand=item.brand, category_hint=item.category_hint,
                         supply_price=item.supply_price, shipping_fee=item.shipping_fee, stock=item.stock,
                         options=item.options, images=item.images, attributes=item.attributes,
                         description=item.description, content_hash="x")
    sp.supplier = supplier
    return sp


SUP = Supplier(code="T", name="t", image_usage_allowed=True, authorized_brands=[])
CAT = {i.sku: i for i in mock_catalog("T")}


def test_unsupported_claims_detected_only_when_not_in_facts():
    facts = "스테인리스 진공 텀블러 소재 스테인리스스틸 304 원산지 중국"
    assert find_unsupported_claims("스테인리스 텀블러", facts) == []
    v = find_unsupported_claims("국내산 KC인증 항균 텀블러", facts)
    kinds = {x.split(":")[0] for x in v}
    assert {"origin", "certification", "efficacy"} <= kinds


def test_rule_processor_outputs():
    sp = _sp(CAT["T-1001"], SUP)
    out = RuleBasedProcessor().process(sp)
    assert out.category_id == "50000001"
    assert out.title and len(out.title) <= 100
    assert all(" " not in t for t in out.tags) and len(out.tags) <= 10
    assert "<script" not in out.detail_html
    assert out.options[0]["values"] == {"색상": "블랙"}


def test_claude_output_guardrail_rejects_hallucinated_facts():
    sp = _sp(CAT["T-1001"], SUP)

    class FakeMessages:
        def parse(self, **kw):
            assert kw["model"] == "claude-opus-5-5"
            return SimpleNamespace(stop_reason="end_turn", parsed_output=ClaudeCopy(
                title="국내산 KC인증 텀블러 500ml",               # 원산지/인증 날조 → 거부
                category_name="생활/건강>주방용품>보온/보냉용품>텀블러",
                tags=["보온텀블러", "국산텀블러", "진공 텀블러"],   # 국산 태그 제거, 공백 제거
                intro="이중 진공 구조로 보온이 오래가는 텀블러입니다.",
            ))

    proc = ClaudeProcessor(client=SimpleNamespace(messages=FakeMessages()), model="claude-opus-5-5")
    out = proc.process(sp)
    assert out.source == "claude"
    assert "국내산" not in out.title and "KC" not in out.title
    assert any(w.startswith("AI_TITLE_REJECTED") for w in out.warnings)
    assert "국산텀블러" not in out.tags and "진공텀블러" in out.tags
    assert out.intro.startswith("이중 진공")


def test_claude_failure_falls_back_to_rules():
    sp = _sp(CAT["T-1001"], SUP)

    class Boom:
        def parse(self, **kw):
            raise RuntimeError("network")

    out = ClaudeProcessor(client=SimpleNamespace(messages=Boom()), model="m").process(sp)
    assert out.source == "rule" and any("AI_ERROR" in w for w in out.warnings)


def test_option_normalization():
    opts = normalize_options([{"name": "color:black / size:m", "sku": "a", "stock": 2}, {"name": "흰색|xl", "sku": "b"}])
    assert opts[0]["values"] == {"color": "블랙", "size": "M"}
    assert opts[1]["values"] == {"옵션1": "화이트", "옵션2": "XL"}


def test_clean_title_removes_promo():
    assert clean_title("[무료배송] 텀블러 텀블러 ★특가★ 500ml") == "텀블러 500ml"


def test_compliance_rules():
    s = DEFAULTS
    assert check_product(_sp(CAT["T-1001"], SUP), SUP, s).ok
    assert any(b.startswith("BRAND_NOT_AUTHORIZED") for b in check_product(_sp(CAT["T-2001"], SUP), SUP, s).blocks)
    assert any(b.startswith("BANNED_KEYWORD") for b in check_product(_sp(CAT["T-2002"], SUP), SUP, s).blocks)
    assert "OUT_OF_STOCK" in check_product(_sp(CAT["T-2003"], SUP), SUP, s).blocks
    assert any(b.startswith("NOTICE_MISSING") for b in check_product(_sp(CAT["T-2006"], SUP), SUP, s).blocks)
    no_img_rights = Supplier(code="X", name="x", image_usage_allowed=False, authorized_brands=[])
    assert any(b.startswith("IMAGE_RIGHTS") for b in check_product(_sp(CAT["T-1001"], no_img_rights), no_img_rights, s).blocks)
    nike_ok = Supplier(code="N", name="n", image_usage_allowed=True, authorized_brands=["나이키"])
    assert check_product(_sp(CAT["T-2001"], nike_ok), nike_ok, s).ok
