from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings
from app.db import SessionLocal, init_db
from app.logging_setup import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    s = get_settings()
    if s.app_env == "production" and (s.jwt_secret.startswith("change-me") or s.service_token.startswith("change-me")):
        raise RuntimeError("운영 환경에서 JWT_SECRET / SERVICE_TOKEN 기본값 사용 금지")
    init_db()
    from app.seed import seed

    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="SmartStore Dropshipping Automation", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins.split(","), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router)


@app.get("/health")
def health():
    s = get_settings()
    return {"ok": True, "naver_mode": s.naver_mode, "safety": {
        "public_listing": s.allow_public_listing, "real_purchase": s.allow_real_purchase,
        "pii_transfer": s.allow_pii_transfer, "naver_order_actions": s.allow_naver_order_actions}}
