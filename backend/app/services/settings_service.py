"""관리자 설정 (DB 저장). 값이 없으면 DEFAULTS 사용."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AppSetting, AuditLog

DEFAULTS: dict[str, Any] = {
    # 자동화
    "auto_listing_enabled": True,        # 검증된 공급사 + 자동등록 허용 공급사에 한해 승인 없이 등록 큐로
    "auto_purchase_enabled": True,       # 발주 API가 있고 자동발주 허용된 공급사에 한해 자동 발주
    "listing_interval_minutes": 60,
    "sourcing_interval_minutes": 180,
    "order_poll_interval_minutes": 5,
    "daily_listing_limit": 30,
    # 가격/마진
    "target_margin_rate": 0.25,          # 판매가(고객결제액) 대비 이익률
    "min_profit_krw": 3000,
    "platform_fee_rates": {              # ⚠ 예시값. 실제 계약/등급별 수수료로 반드시 수정
        "naver_order_management_fee": 0.0363,
        "naver_sales_linkage_fee": 0.02,
    },
    "ad_cost_rate": 0.03,                # 판매가 대비 광고비 배분율
    "ad_cost_per_order": 0,
    "other_variable_cost": 500,          # 포장/CS/반품충당 등 주문당 변동비
    "customer_shipping_fee": 0,          # 고객 부담 배송비 (0 = 무료배송)
    "price_rounding_unit": 100,
    "max_supply_price_increase_rate": 0.05,  # 주문 시 공급가 상승 허용치 (초과 시 보류)
    # 발주 안전장치
    "daily_purchase_amount_limit": 1000000,
    "max_purchase_retries": 3,
    # 정책
    "banned_keywords": [
        "의약품", "전문의약품", "담배", "전자담배", "주류", "총포", "도검", "마약",
        "레플리카", "이미테이션", "짝퉁", "미러급", "정품급", "콘택트렌즈", "건강기능식품",
    ],
    # 코드 매핑 (운영 전 네이버 문서로 확인 후 입력)
    "origin_area_codes": {},   # {"중국": "<네이버 원산지코드>", ...}  GET /v1/product-origin-areas
    "carrier_code_map": {},    # 기본 매핑(app/naver/carriers.py)에 덮어쓸 {공급사코드: 네이버코드}
    "restricted_claims": [
        "치료", "완치", "특효", "예방", "부작용 없", "100% 효과", "의학적", "FDA", "식약처 인증",
    ],
}


def get_setting(db: Session, key: str) -> Any:
    row = db.get(AppSetting, key)
    if row is None:
        return DEFAULTS.get(key)
    return row.value


def get_all_settings(db: Session) -> dict[str, Any]:
    out = dict(DEFAULTS)
    for row in db.query(AppSetting).all():
        out[row.key] = row.value
    return out


def update_settings(db: Session, values: dict[str, Any], actor: str) -> dict[str, Any]:
    unknown = set(values) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"알 수 없는 설정 키: {sorted(unknown)}")
    _validate(values)
    for key, value in values.items():
        row = db.get(AppSetting, key)
        old = row.value if row else DEFAULTS.get(key)
        if row is None:
            db.add(AppSetting(key=key, value=value, updated_by=actor))
        else:
            row.value = value
            row.updated_by = actor
        db.add(AuditLog(actor=actor, action="setting.update", entity="setting", entity_id=key,
                        detail={"old": old, "new": value}))
    db.flush()
    return get_all_settings(db)


def _validate(values: dict[str, Any]) -> None:
    rate_keys = ("target_margin_rate", "ad_cost_rate", "max_supply_price_increase_rate")
    for k in rate_keys:
        if k in values and not (0 <= float(values[k]) < 1):
            raise ValueError(f"{k} 는 0 이상 1 미만이어야 합니다")
    if "platform_fee_rates" in values:
        fees = values["platform_fee_rates"]
        if not isinstance(fees, dict) or any(not (0 <= float(v) < 1) for v in fees.values()):
            raise ValueError("platform_fee_rates 는 {이름: 0~1 비율} 형태여야 합니다")
    for k in ("daily_listing_limit", "listing_interval_minutes", "daily_purchase_amount_limit", "min_profit_krw"):
        if k in values and int(values[k]) < 0:
            raise ValueError(f"{k} 는 음수가 될 수 없습니다")
