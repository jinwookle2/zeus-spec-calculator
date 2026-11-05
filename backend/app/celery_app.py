"""Celery 워커/비트. 실패 시 지수 백오프 재시도, 최종 실패는 DLQ(dead_letters) 기록."""
from __future__ import annotations

from celery import Celery

from app.config import get_settings
from app.db import session_scope
from app.jobs import JOBS, run_job

s = get_settings()
celery = Celery("dropship", broker=s.redis_url, backend=s.redis_url)
celery.conf.update(
    task_always_eager=s.celery_eager,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Seoul",
    # 실행 주기는 관리자 설정(자동화 설정 메뉴)을 따르도록 1분마다 tick 에서 판단
    beat_schedule={"tick": {"task": "jobs.tick", "schedule": 60.0}},
)
# 동시 실행 방지용 Redis 락 TTL (초)
LOCK_TTL = 900


@celery.task(name="jobs.run", bind=True, max_retries=3)
def run_job_task(self, name: str):
    if name not in JOBS:
        raise ValueError(name)
    lock = None
    if not s.celery_eager:
        import redis

        lock = redis.Redis.from_url(s.redis_url).lock(f"lock:job:{name}", timeout=LOCK_TTL, blocking=False)
        if not lock.acquire():
            return {"skipped": "already running"}
    try:
        return run_job(name)
    except Exception as e:
        if self.request.retries >= self.max_retries:
            from app.services.alerts import dead_letter

            with session_scope() as db:
                dead_letter(db, f"jobs.run:{name}", {"job": name}, str(e), self.request.retries + 1)
            raise
        raise self.retry(exc=e, countdown=30 * 2 ** self.request.retries)
    finally:
        if lock is not None:
            try:
                lock.release()
            except Exception:  # noqa: BLE001
                pass


@celery.task(name="jobs.tick")
def tick():
    from app.jobs import due_jobs

    due = due_jobs()
    for name in due:
        run_job_task.delay(name)
    return due
