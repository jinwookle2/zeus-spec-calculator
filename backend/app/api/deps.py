from __future__ import annotations

import hmac
from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Role, User
from app.security import decode_access_token, has_role

bearer = HTTPBearer(auto_error=False)


@dataclass
class Principal:
    email: str
    role: Role


def current_principal(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_service_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Principal:
    if x_service_token:
        if hmac.compare_digest(x_service_token, get_settings().service_token):
            return Principal("service:n8n", Role.OPERATOR)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid service token")
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "로그인이 필요합니다")
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "토큰이 유효하지 않습니다") from None
    user = db.query(User).filter_by(email=payload["sub"], active=True).one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "비활성 사용자")
    return Principal(user.email, user.role)


def require(role: Role):
    def dep(p: Principal = Depends(current_principal)) -> Principal:
        if not has_role(p.role, role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"{role.value} 권한 필요")
        return p

    return dep


viewer = require(Role.VIEWER)
operator = require(Role.OPERATOR)
admin = require(Role.ADMIN)
