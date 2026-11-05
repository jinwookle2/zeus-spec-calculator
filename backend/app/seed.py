"""초기 데이터: 관리자 계정 + Mock 공급사."""
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Role, Supplier, User
from app.security import hash_password


def seed(db: Session) -> None:
    s = get_settings()
    if not db.query(User).filter_by(email=s.bootstrap_admin_email).first():
        db.add(User(email=s.bootstrap_admin_email, password_hash=hash_password(s.bootstrap_admin_password), role=Role.ADMIN))
    if not db.query(Supplier).first():
        # 검증 완료된 Mock 공급사 (자동 등록/자동 발주 허용) — 단계적 자동화 시연용
        db.add(Supplier(code="MOCKA", name="목업도매 A (검증됨)", adapter_type="mock", config={"prefix": "MA"},
                        verified=True, auto_listing_allowed=True, auto_purchase_allowed=True, purchase_api_available=True,
                        image_usage_allowed=True, authorized_brands=[], contract_note="Mock: 이미지 사용/자동발주 허용"))
        # 미검증 Mock 공급사 → 등록·발주 모두 관리자 승인
        db.add(Supplier(code="MOCKB", name="목업도매 B (미검증)", adapter_type="mock", config={"prefix": "MB", "name_suffix": "B타입"},
                        verified=False, image_usage_allowed=True))
    db.commit()
