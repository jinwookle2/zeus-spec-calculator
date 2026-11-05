import logging
import sys

import structlog

from app.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    renderer = structlog.processors.JSONRenderer(ensure_ascii=False) if settings.log_json else structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    )
    if settings.sentry_dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.app_env, send_default_pii=False)


log = structlog.get_logger()
