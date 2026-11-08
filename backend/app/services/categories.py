"""네이버 카테고리 동기화 (GET /v1/categories, 약 5,800개)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import NaverCategory, utcnow
from app.naver.client import NaverClient
from app.services.ai_processor import MOCK_CATEGORIES


def sync_categories(db: Session, naver: NaverClient) -> dict:
    rows = naver.get_categories()
    existing = {c.id: c for c in db.query(NaverCategory)}
    created = updated = 0
    now = utcnow()
    for r in rows:
        cid = str(r["id"])
        whole = r.get("wholeCategoryName") or r.get("name") or ""
        c = existing.get(cid)
        if c is None:
            db.add(NaverCategory(id=cid, name=r.get("name") or whole.split(">")[-1], whole_name=whole,
                                 last=bool(r.get("last")), synced_at=now))
            created += 1
        else:
            c.name, c.whole_name, c.last, c.synced_at = r.get("name") or c.name, whole, bool(r.get("last")), now
            updated += 1
    db.flush()
    return {"fetched": len(rows), "created": created, "updated": updated}


def load_category_map(db: Session) -> dict[str, str]:
    """{전체 카테고리명: 리프 카테고리 ID}. 동기화 전이면 Mock 사전."""
    rows = db.query(NaverCategory.whole_name, NaverCategory.id).filter(NaverCategory.last.is_(True)).all()
    return {w: i for w, i in rows} if rows else dict(MOCK_CATEGORIES)
