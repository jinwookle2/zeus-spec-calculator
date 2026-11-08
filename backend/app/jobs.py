"""스케줄 작업 정의. Celery beat, n8n, 관리자 '지금 실행' 버튼이 모두 이 함수를 호출한다."""
from __future__ import annotations

from collections.abc import Callable

from app.db import session_scope
from app.logging_setup import log
from app.models import JobRun, utcnow
from app.naver.client import get_naver_client
from app.services import categories, fulfillment, listing, settlement, sourcing

JOBS: dict[str, Callable] = {
    "source_products": lambda db, nv: {"suppliers": sourcing.sync_all_suppliers(db)},
    "process_candidates": lambda db, nv: listing.process_new_candidates(db),
    "publish_listings": lambda db, nv: listing.publish_approved(db, nv),
    "sync_inventory": lambda db, nv: listing.sync_inventory(db, nv),
    "collect_orders": lambda db, nv: fulfillment.collect_orders(db, nv),
    "process_orders": lambda db, nv: fulfillment.process_paid_orders(db, nv),
    "retry_purchases": lambda db, nv: fulfillment.retry_pending_purchases(db, nv),
    "poll_shipments": lambda db, nv: fulfillment.poll_shipments(db, nv),
    "sync_categories": lambda db, nv: categories.sync_categories(db, nv),
    "reconcile_settlements": lambda db, nv: settlement.reconcile_settlements(db, nv),
}

PIPELINE = ["source_products", "process_candidates", "publish_listings", "sync_inventory",
            "collect_orders", "process_orders", "retry_purchases", "poll_shipments"]


def run_job(name: str) -> dict:
    if name not in JOBS:
        raise KeyError(name)
    started = utcnow()
    try:
        with session_scope() as db:
            result = JOBS[name](db, get_naver_client(db))
            db.add(JobRun(job=name, success=True, summary=_jsonable(result), started_at=started, finished_at=utcnow()))
        log.info("job.done", job=name, result=result)
        return result
    except Exception as e:
        log.exception("job.failed", job=name)
        with session_scope() as db:
            from app.services.alerts import raise_alert

            db.add(JobRun(job=name, success=False, summary={"error": str(e)}, started_at=started, finished_at=utcnow()))
            raise_alert(db, "error", "job", f"작업 실패: {name}: {e}")
        raise


def run_pipeline() -> dict:
    return {name: run_job(name) for name in PIPELINE}


def _jsonable(o):
    import json

    return json.loads(json.dumps(o, default=str))


# 작업별 실행 주기(분)를 가져올 설정 키 (없으면 고정값)
INTERVAL_KEYS = {
    "source_products": "sourcing_interval_minutes",
    "process_candidates": "listing_interval_minutes",
    "publish_listings": "listing_interval_minutes",
    "collect_orders": "order_poll_interval_minutes",
    "process_orders": "order_poll_interval_minutes",
    "retry_purchases": "order_poll_interval_minutes",
}
FIXED_INTERVALS = {"sync_inventory": 30, "poll_shipments": 30, "sync_categories": 1440, "reconcile_settlements": 360}
SCHEDULED = PIPELINE + ["sync_categories", "reconcile_settlements"]


def due_jobs() -> list[str]:
    from datetime import timedelta

    from sqlalchemy import func

    from app.services.settings_service import get_all_settings

    with session_scope() as db:
        s = get_all_settings(db)
        last = dict(db.query(JobRun.job, func.max(JobRun.started_at)).group_by(JobRun.job).all())
        now = utcnow()
        due = []
        for name in SCHEDULED:
            minutes = int(s.get(INTERVAL_KEYS.get(name, ""), FIXED_INTERVALS.get(name, 60)) or 60)
            prev = last.get(name)
            if prev is not None and prev.tzinfo is None:
                from datetime import timezone

                prev = prev.replace(tzinfo=timezone.utc)
            if prev is None or now - prev >= timedelta(minutes=minutes):
                due.append(name)
        return due
