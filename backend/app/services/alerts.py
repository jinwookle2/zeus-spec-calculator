from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.logging_setup import log
from app.models import Alert, AuditLog, DeadLetter


def raise_alert(db: Session, level: str, category: str, message: str, detail: dict | None = None) -> Alert:
    alert = Alert(level=level, category=category, message=message[:500], detail=detail or {})
    db.add(alert)
    log.warning("alert", level=level, category=category, message=message)
    url = get_settings().alert_webhook_url
    if url and level in ("error", "critical", "warning"):
        try:  # Slack/Telegram/n8n webhook 등. 실패해도 업무 흐름은 계속.
            httpx.post(url, json={"text": f"[{level.upper()}] {category}: {message}", "detail": detail or {}}, timeout=5)
        except httpx.HTTPError as e:
            log.error("alert.webhook_failed", error=str(e))
    return alert


def audit(db: Session, actor: str, action: str, entity: str, entity_id: str | int | None, **detail) -> None:
    db.add(AuditLog(actor=actor, action=action, entity=entity, entity_id=str(entity_id) if entity_id else None,
                    detail=detail))


def dead_letter(db: Session, task_name: str, payload: dict, error: str, attempts: int) -> None:
    db.add(DeadLetter(task_name=task_name, payload=payload, error=error[:4000], attempts=attempts))
    raise_alert(db, "error", "dead_letter", f"{task_name} 최종 실패 → DLQ 이동", {"payload": payload, "error": error[:500]})
