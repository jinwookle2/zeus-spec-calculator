"""환경변수 기반 설정. 비밀값은 반드시 환경변수 또는 Secret Manager로 주입한다."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "test", "staging", "production"] = "local"
    database_url: str = "sqlite:///./dropship.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_eager: bool = False

    # 인증
    jwt_secret: str = "change-me-in-production"
    jwt_expire_minutes: int = 480
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = "admin1234!"
    # n8n 등 서버 간 호출용 토큰
    service_token: str = "change-me-service-token"

    # 개인정보 암호화 키 (Fernet, urlsafe base64 32바이트)
    pii_encryption_key: str = ""

    # 네이버 커머스 API
    naver_mode: Literal["mock", "live"] = "mock"
    naver_base_url: str = "https://api.commerce.naver.com/external"
    naver_client_id: str = ""
    naver_client_secret: str = ""
    naver_token_type: Literal["SELF", "SELLER"] = "SELF"
    naver_account_id: str = ""
    naver_sign_b64: Literal["standard", "urlsafe"] = "standard"
    naver_rps: float = 2.0

    # ---- 안전 스위치: 명시적으로 true로 바꾸기 전까지 실제 외부 효과 없음 ----
    allow_public_listing: bool = False   # 네이버 실제 상품 공개 등록/수정
    allow_real_purchase: bool = False    # 공급사 실제 발주/결제
    allow_pii_transfer: bool = False     # 고객 개인정보 공급사 전송
    allow_naver_order_actions: bool = False  # 네이버 발주확인/발송처리 실제 호출

    # Claude API
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"
    ai_enabled: bool = True

    # 모니터링/알림
    sentry_dsn: str = ""
    alert_webhook_url: str = ""
    log_json: bool = True

    cors_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
