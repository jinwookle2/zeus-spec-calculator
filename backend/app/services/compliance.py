"""판매 금지/브랜드 권리/이미지 권한/고시정보 검증 (결정적 규칙, AI 미사용)."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Supplier, SupplierProduct

REQUIRED_NOTICE_FIELDS = ("manufacturer", "origin")


@dataclass
class ComplianceResult:
    blocks: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blocks


def check_product(sp: SupplierProduct, supplier: Supplier, settings: dict) -> ComplianceResult:
    res = ComplianceResult()
    text = " ".join(filter(None, [sp.name, sp.description or "", sp.category_hint or ""]))

    for kw in settings.get("banned_keywords", []):
        if kw and kw in text:
            res.blocks.append(f"BANNED_KEYWORD: {kw}")
    for kw in settings.get("restricted_claims", []):
        if kw and kw in text:
            res.blocks.append(f"RESTRICTED_CLAIM: {kw}")

    brand = (sp.brand or "").strip()
    if brand and brand.lower() not in {"없음", "자체제작", "noname", "no brand", "기타"}:
        authorized = {b.lower() for b in (supplier.authorized_brands or [])}
        if brand.lower() not in authorized:
            res.blocks.append(f"BRAND_NOT_AUTHORIZED: '{brand}' 판매 권한 확인 필요")

    if not supplier.image_usage_allowed:
        res.blocks.append("IMAGE_RIGHTS_UNCONFIRMED: 공급사 이미지 사용 허락 미확인")
    if not sp.images:
        res.blocks.append("NO_IMAGE")

    attrs = sp.attributes or {}
    for f in REQUIRED_NOTICE_FIELDS:
        if not attrs.get(f):
            res.blocks.append(f"NOTICE_MISSING: {f}")
    if not attrs.get("notice"):
        res.warnings.append("NOTICE_DETAIL_MISSING: 상품군별 고시정보 상세 없음 → 등록 전 확인")

    if sp.stock <= 0:
        res.blocks.append("OUT_OF_STOCK")
    if sp.supply_price <= 0:
        res.blocks.append("INVALID_SUPPLY_PRICE")
    return res
