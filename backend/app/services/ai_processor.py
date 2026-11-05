"""AI 상품 가공.

원칙
- AI 는 '표현'만 다듬는다. 브랜드/인증/원산지/소재/효능 같은 '사실'은 공급사 원본 데이터에서만 가져온다.
- AI 출력은 guardrail 로 검사하고, 원본에 없는 민감 사실이 나오면 해당 필드를 규칙 기반 결과로 대체한다.
- ANTHROPIC_API_KEY 가 없거나 호출이 실패하면 규칙 기반(RuleBasedProcessor)으로 동작한다.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.config import get_settings
from app.logging_setup import log
from app.models import SupplierProduct

# Mock 카테고리 (실 운영 시 GET /v1/categories 결과를 동기화해서 사용)
MOCK_CATEGORIES: dict[str, str] = {
    "생활/건강>주방용품>보온/보냉용품>텀블러": "50000001",
    "생활/건강>수납/정리용품>수납바구니": "50000002",
    "가구/인테리어>인테리어소품>조명>스탠드": "50000003",
    "생활/건강>반려동물>급식/급수용품>급수기": "50000004",
    "생활/건강>자동차용품>차량용 거치대": "50000005",
    "스포츠/레저>캠핑>캠핑가구>캠핑의자": "50000006",
    "생활/건강>주방용품>조리도구>도마": "50000007",
    "생활/건강>생활용품>방향제>디퓨저": "50000008",
    "디지털/가전>주방가전>전기포트": "50000009",
    "패션잡화>지갑>카드지갑": "50000010",
    "디지털/가전>음향가전>이어폰": "50000011",
    "패션잡화>남녀공용신발>운동화": "50000012",
}

SENSITIVE_PATTERNS: dict[str, str] = {
    "certification": r"KC\s?인증|KC|인증|특허|FDA|CE\s?인증|친환경\s?인증|HACCP",
    "origin": r"국산|국내산|국내\s?제조|한국산|Made\s?in\s?\w+|일본산|독일산|미국산|이탈리아산|수입산",
    "material": r"스테인리스(?:스틸)?(?:\s?\d{3})?|실리콘|원목|천연\s?가죽|소가죽|순면|면\s?\d+\s?%|유기농|오가닉|캐시미어|울\s?\d+\s?%|티타늄",
    "efficacy": r"효능|효과|치료|개선|예방|항균|살균|탈취|99\.9\s?%|피부\s?진정|숙면",
    "brand": r"정품|명품|공식\s?수입|본사\s?정품|나이키|아디다스|삼성|애플|다이슨|스탠리|락앤락|써모스",
}

COLOR_MAP = {"black": "블랙", "white": "화이트", "red": "레드", "blue": "블루", "gray": "그레이", "grey": "그레이",
             "검정": "블랙", "검정색": "블랙", "흰색": "화이트", "하양": "화이트", "빨강": "레드", "파랑": "블루", "회색": "그레이"}


def facts_text(sp: SupplierProduct) -> str:
    attrs = sp.attributes or {}
    parts = [sp.name, sp.brand or "", sp.description or "", sp.category_hint or ""]
    parts += [str(v) for k, v in attrs.items() if k != "notice"]
    parts += [str(v) for v in (attrs.get("notice") or {}).values()]
    return " ".join(parts)


def find_unsupported_claims(text: str, facts: str) -> list[str]:
    """출력 텍스트에서 원본 사실에 없는 민감 표현을 찾는다."""
    violations = []
    facts_norm = re.sub(r"\s+", "", facts).lower()
    for kind, pattern in SENSITIVE_PATTERNS.items():
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            token = re.sub(r"\s+", "", m.group(0)).lower()
            if token not in facts_norm:
                violations.append(f"{kind}:{m.group(0)}")
    return violations


@dataclass
class ProcessedContent:
    title: str
    category_id: str | None
    category_name: str | None
    tags: list[str]
    intro: str
    options: list[dict]
    notice: dict
    detail_html: str
    source: str = "rule"
    warnings: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ 규칙 기반


def clean_title(name: str, brand: str | None = None, max_len: int = 100) -> str:
    t = re.sub(r"[\[\]【】()<>{}★☆♥♡!~^*#@]+", " ", name)
    t = re.sub(r"\b(무료배송|최저가|특가|당일발송|빠른배송|초특가|1\+1)\b", " ", t)
    words, seen = [], set()
    for w in t.split():
        if w.lower() not in seen:
            seen.add(w.lower())
            words.append(w)
    title = " ".join(words)
    return title[:max_len].strip()


def recommend_category(sp: SupplierProduct, categories: dict[str, str] = MOCK_CATEGORIES) -> tuple[str | None, str | None]:
    hint_tokens = set(re.split(r"[>/\s]+", (sp.category_hint or "") + " " + sp.name)) - {""}
    best, best_score = None, 0
    for name in categories:
        leaf_tokens = set(re.split(r"[>/\s]+", name)) - {""}
        score = len(hint_tokens & leaf_tokens) * 2 + sum(1 for t in leaf_tokens if t in sp.name)
        if score > best_score:
            best, best_score = name, score
    return (categories[best], best) if best else (None, None)


def recommend_tags(title: str, category_name: str | None, limit: int = 10) -> list[str]:
    tokens = [re.sub(r"[^\w가-힣]", "", w) for w in title.split()]
    if category_name:
        tokens += [category_name.split(">")[-1].replace(" ", "")]
    tags: list[str] = []
    for t in tokens:
        if len(t) >= 2 and not t.isdigit() and t not in tags:
            tags.append(t)
    return tags[:limit]


def normalize_options(options: list[dict]) -> list[dict]:
    out = []
    for i, o in enumerate(options or []):
        raw = str(o.get("name", "")).strip()
        values: dict[str, str] = {}
        for part in re.split(r"\s*[/|,]\s*", raw):
            if not part:
                continue
            if ":" in part:
                k, v = (x.strip() for x in part.split(":", 1))
            else:
                k, v = f"옵션{len(values) + 1}", part.strip()
            v = COLOR_MAP.get(v.lower(), v)
            if re.fullmatch(r"(xs|s|m|l|xl|xxl|free)", v, re.I):
                v = v.upper()
            values[k] = v
        out.append({
            "values": values,
            "label": " / ".join(f"{k}:{v}" for k, v in values.items()),
            "sku": o.get("sku") or f"opt-{i}",
            "stock": int(o["stock"]) if o.get("stock") is not None else 0,
            "extra_price": int(o.get("extra_price") or 0),
        })
    return out


def build_notice(sp: SupplierProduct) -> dict:
    """공급사 고시정보 → 네이버 고시정보(ETC 상품군 기준). 상품군별 필드는 운영 전 확인 필요."""
    attrs = sp.attributes or {}
    n = attrs.get("notice") or {}
    return {
        "productInfoProvidedNoticeType": "ETC",
        "etc": {
            "itemName": n.get("품명") or sp.name,
            "modelName": n.get("모델명") or sp.supplier_sku,
            "manufacturer": n.get("제조자") or attrs.get("manufacturer") or "",
            "afterServiceDirector": n.get("A/S 책임자와 전화번호") or "",
            "certificateDetails": attrs.get("certifications") or "해당사항 없음",
        },
    }


def render_detail_html(sp: SupplierProduct, title: str, intro: str, options: list[dict], images: list[str]) -> str:
    e = html.escape
    attrs = sp.attributes or {}
    rows = [("제조사", attrs.get("manufacturer")), ("원산지", attrs.get("origin")), ("소재", attrs.get("material")),
            ("브랜드", sp.brand)]
    rows_html = "".join(f"<tr><th style='text-align:left;padding:6px 12px;background:#f5f5f5'>{e(k)}</th>"
                        f"<td style='padding:6px 12px'>{e(str(v))}</td></tr>" for k, v in rows if v)
    opts_html = "".join(f"<li>{e(o['label'])}</li>" for o in options)
    imgs_html = "".join(f"<p style='margin:0'><img src='{e(u)}' alt='{e(title)}' style='max-width:100%'/></p>" for u in images)
    return (
        "<div style='max-width:860px;margin:0 auto;font-family:sans-serif;line-height:1.6'>"
        f"<h2 style='font-size:22px'>{e(title)}</h2>"
        f"<p>{e(intro)}</p>"
        f"{imgs_html}"
        + (f"<h3>옵션</h3><ul>{opts_html}</ul>" if opts_html else "")
        + (f"<h3>상품 정보</h3><table style='border-collapse:collapse;width:100%'>{rows_html}</table>" if rows_html else "")
        + "<p style='color:#888;font-size:12px'>상품 정보는 공급사 제공 자료 기준이며, 상세 고시정보는 상품정보제공고시를 확인해 주세요.</p>"
        "</div>"
    )


class RuleBasedProcessor:
    source = "rule"

    def process(self, sp: SupplierProduct, image_urls: list[str] | None = None) -> ProcessedContent:
        title = clean_title(sp.name, sp.brand)
        cat_id, cat_name = recommend_category(sp)
        tags = recommend_tags(title, cat_name)
        options = normalize_options(sp.options)
        intro = f"{title} 상품입니다."
        images = image_urls or sp.images
        warnings = [] if cat_id else ["CATEGORY_NOT_FOUND: 카테고리 수동 지정 필요"]
        return ProcessedContent(title, cat_id, cat_name, tags, intro, options, build_notice(sp),
                                render_detail_html(sp, title, intro, options, images), self.source, warnings)


# ------------------------------------------------------------------ Claude


class ClaudeCopy(BaseModel):
    title: str = Field(description="네이버 스마트스토어 상품명 (최대 50자, 특수문자/홍보문구/브랜드 추가 금지)")
    category_name: str = Field(description="제공된 카테고리 후보 중 정확히 하나")
    tags: list[str] = Field(description="검색 태그 최대 10개, 띄어쓰기 없이")
    intro: str = Field(description="상세페이지 도입 문구 2~3문장. 제공된 사실만 사용")


SYSTEM_PROMPT = """너는 네이버 스마트스토어 상품 등록 담당자다. 공급사가 준 '사실'만 사용해 상품명, 카테고리, 검색 태그, 도입 문구를 만든다.
- 사실에 없는 브랜드, 인증(KC/특허 등), 원산지, 소재, 효능·효과를 절대 쓰지 않는다. 불확실하면 생략한다.
- 과장/최상급 표현, '무료배송/최저가' 같은 홍보 문구, 특수문자를 상품명에 넣지 않는다.
- 카테고리는 반드시 주어진 후보 중 하나를 그대로 고른다."""


class ClaudeProcessor:
    source = "claude"

    def __init__(self, client=None, model: str | None = None):
        import anthropic

        self.client = client or anthropic.Anthropic(api_key=get_settings().anthropic_api_key or None)
        self.model = model or get_settings().claude_model
        self.fallback = RuleBasedProcessor()

    def process(self, sp: SupplierProduct, image_urls: list[str] | None = None) -> ProcessedContent:
        base = self.fallback.process(sp, image_urls)
        facts = facts_text(sp)
        user = (
            f"[공급사 사실]\n상품명: {sp.name}\n브랜드: {sp.brand or '없음'}\n분류 힌트: {sp.category_hint or ''}\n"
            f"속성: { {k: v for k, v in (sp.attributes or {}).items() if k != 'notice'} }\n"
            f"설명: {sp.description or ''}\n옵션: {[o['label'] for o in base.options]}\n\n"
            f"[카테고리 후보]\n" + "\n".join(MOCK_CATEGORIES)
        )
        try:
            resp = self.client.messages.parse(
                model=self.model, max_tokens=2000, system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user}], output_format=ClaudeCopy,
            )
            if resp.stop_reason == "refusal" or resp.parsed_output is None:
                base.warnings.append("AI_REFUSED_OR_EMPTY: 규칙 기반 결과 사용")
                return base
            out: ClaudeCopy = resp.parsed_output
        except Exception as e:  # noqa: BLE001 - 어떤 오류든 규칙 기반으로 대체
            log.warning("ai.claude_failed", error=str(e), sku=sp.supplier_sku)
            base.warnings.append(f"AI_ERROR: {type(e).__name__} → 규칙 기반 결과 사용")
            return base
        return merge_ai_output(base, out, sp, facts, image_urls)


def merge_ai_output(base: ProcessedContent, out: ClaudeCopy, sp: SupplierProduct, facts: str,
                    image_urls: list[str] | None) -> ProcessedContent:
    result = ProcessedContent(**{**base.__dict__, "warnings": list(base.warnings)})
    result.source = "claude"
    title = clean_title(out.title)
    v = find_unsupported_claims(title, facts)
    if v or not title:
        result.warnings.append(f"AI_TITLE_REJECTED: {v}")
    else:
        result.title = title
    if out.category_name in MOCK_CATEGORIES:
        result.category_name, result.category_id = out.category_name, MOCK_CATEGORIES[out.category_name]
    tags = [re.sub(r"\s+", "", t) for t in out.tags if t.strip()]
    tags = [t for t in dict.fromkeys(tags) if not find_unsupported_claims(t, facts)][:10]
    if tags:
        result.tags = tags
    v = find_unsupported_claims(out.intro, facts)
    if v:
        result.warnings.append(f"AI_INTRO_REJECTED: {v}")
    else:
        result.intro = out.intro.strip()
    result.detail_html = render_detail_html(sp, result.title, result.intro, result.options, image_urls or sp.images)
    return result


def get_processor():
    s = get_settings()
    if s.ai_enabled and s.anthropic_api_key:
        return ClaudeProcessor()
    return RuleBasedProcessor()
