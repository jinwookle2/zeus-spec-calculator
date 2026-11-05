import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", os.environ.get("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db"))
os.environ["APP_ENV"] = "test"
os.environ["NAVER_MODE"] = "mock"
os.environ["CELERY_EAGER"] = "true"
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["ALERT_WEBHOOK_URL"] = ""
os.environ["LOG_JSON"] = "false"
os.environ["JWT_SECRET"] = "test-secret-0123456789abcdef0123456789abcdef"
os.environ["SERVICE_TOKEN"] = "test-service-token"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import db as dbmod  # noqa: E402
from app.db import Base  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.naver.client import MockNaverClient  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(dbmod.engine)
    Base.metadata.create_all(dbmod.engine)
    with dbmod.SessionLocal() as s:
        seed(s)
        s.add(User(email="op@example.com", password_hash=hash_password("operator123"), role=Role.OPERATOR))
        s.add(User(email="viewer@example.com", password_hash=hash_password("viewer1234"), role=Role.VIEWER))
        s.commit()
    MockNaverClient.fail_listing_keys = set()
    yield


@pytest.fixture
def db():
    s = dbmod.SessionLocal()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


def _login(client, email, pw):
    r = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin_h(client):
    return _login(client, "admin@example.com", "admin1234!")


@pytest.fixture
def op_h(client):
    return _login(client, "op@example.com", "operator123")


@pytest.fixture
def viewer_h(client):
    return _login(client, "viewer@example.com", "viewer1234")
