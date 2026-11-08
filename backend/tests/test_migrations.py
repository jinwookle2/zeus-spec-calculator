"""alembic 마이그레이션이 현재 모델과 일치하는지 검증 (새 모델 추가 시 revision 누락 방지)."""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db import Base, run_migrations


def test_migrations_match_models(tmp_path):
    url = f"sqlite:///{tmp_path}/mig.db"
    run_migrations(url)
    engine = create_engine(url)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": False}), Base.metadata)
        tables = set(inspect(conn).get_table_names())
    assert {"orders", "purchase_orders", "settlements", "naver_categories", "alembic_version"} <= tables
    assert diff == [], f"모델 변경에 대한 마이그레이션이 없습니다: {diff}"
