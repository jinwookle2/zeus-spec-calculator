"""인증, 역할 권한, 개인정보 암호화."""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings
from app.models import Role

ROLE_LEVEL = {Role.VIEWER: 1, Role.OPERATOR: 2, Role.ADMIN: 3}


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode(), bcrypt.gensalt()).decode()


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(email: str, role: Role) -> str:
    s = get_settings()
    payload = {
        "sub": email,
        "role": role.value,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])


def has_role(user_role: Role, required: Role) -> bool:
    return ROLE_LEVEL[user_role] >= ROLE_LEVEL[required]


# ---------------- 개인정보 암호화 ----------------

def _fernet() -> Fernet:
    key = get_settings().pii_encryption_key
    if not key:
        s = get_settings()
        if s.app_env in ("production", "staging"):
            raise RuntimeError("PII_ENCRYPTION_KEY 가 설정되지 않았습니다")
        # 로컬/테스트 전용 파생 키 (운영 금지)
        key = base64.urlsafe_b64encode(hashlib.sha256(s.jwt_secret.encode()).digest()).decode()
    return Fernet(key.encode())


def encrypt_pii(value: str | None) -> str | None:
    if value is None:
        return None
    return _fernet().encrypt(value.encode()).decode()


def decrypt_pii(token: str | None) -> str | None:
    if token is None:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def mask_name(name: str | None) -> str | None:
    if not name:
        return name
    return name[0] + "*" * (len(name) - 1) if len(name) > 1 else "*"


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return phone
    digits = phone.replace("-", "")
    return digits[:3] + "-****-" + digits[-4:] if len(digits) >= 8 else "****"


def mask_address(addr: str | None) -> str | None:
    if not addr:
        return addr
    parts = addr.split()
    return " ".join(parts[:2]) + " ***" if len(parts) > 2 else "***"


# ---------------- 2단계 인증 (TOTP, RFC 6238) ----------------
import hmac as _hmac
import secrets as _secrets
import struct as _struct
import time as _time
from urllib.parse import quote as _quote


def new_totp_secret() -> str:
    return base64.b32encode(_secrets.token_bytes(20)).decode().rstrip("=")


def totp_code(secret: str, for_time: float | None = None, step: int = 30, digits: int = 6) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    counter = int((for_time if for_time is not None else _time.time()) // step)
    digest = _hmac.new(key, _struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (_struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(value).zfill(digits)


def verify_totp(secret: str, code: str | None, window: int = 1) -> bool:
    if not code or not code.strip().isdigit():
        return False
    now = _time.time()
    return any(_hmac.compare_digest(totp_code(secret, now + i * 30), code.strip()) for i in range(-window, window + 1))


def totp_uri(secret: str, email: str, issuer: str = "SmartStore-Automation") -> str:
    return f"otpauth://totp/{_quote(issuer)}:{_quote(email)}?secret={secret}&issuer={_quote(issuer)}&digits=6&period=30"
