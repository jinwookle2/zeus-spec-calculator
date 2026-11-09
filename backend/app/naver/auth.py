"""네이버 커머스 API OAuth2 (client_credentials + bcrypt 전자서명).

근거: 공식 OpenAPI 스펙 (github.com/commerce-api-naver/commerce-api docs/2.0.0-RC.js)
  POST /v1/oauth2/token  (query/form) client_id, timestamp(ms), client_secret_sign, grant_type=client_credentials, type=SELF|SELLER
  client_secret_sign = base64( bcrypt.hashpw(f"{client_id}_{timestamp}", client_secret) )
  토큰 유효 3시간. 남은 시간이 30분 이상이면 기존 토큰이 재반환된다.
공식 Java 예제는 URL-safe Base64, Python 예제는 표준 Base64 를 사용 → NAVER_SIGN_B64 로 선택.
"""
from __future__ import annotations

import base64
import threading
import time
from dataclasses import dataclass

import bcrypt


def make_signature(client_id: str, client_secret: str, timestamp_ms: int, encoding: str = "standard") -> str:
    password = f"{client_id}_{timestamp_ms}".encode()
    hashed = bcrypt.hashpw(password, client_secret.encode())
    if encoding == "urlsafe":
        return base64.urlsafe_b64encode(hashed).decode()
    return base64.standard_b64encode(hashed).decode()


@dataclass
class Token:
    access_token: str
    expires_at: float

    def valid(self, margin_sec: int = 600) -> bool:
        return time.time() < self.expires_at - margin_sec


class TokenManager:
    """토큰 캐시 + 만료 10분 전 자동 갱신 (스레드 안전)."""

    def __init__(self, fetcher):
        self._fetcher = fetcher  # () -> (access_token, expires_in)
        self._token: Token | None = None
        self._lock = threading.Lock()

    def get(self) -> str:
        with self._lock:
            if self._token is None or not self._token.valid():
                access, expires_in = self._fetcher()
                self._token = Token(access, time.time() + int(expires_in))
            return self._token.access_token

    def invalidate(self) -> None:
        with self._lock:
            self._token = None
