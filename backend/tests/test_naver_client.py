import base64
import json

import bcrypt
import httpx
import pytest

from app.config import Settings
from app.models import ApiCallLog
from app.naver.auth import TokenManager, make_signature
from app.naver.carriers import map_carrier
from app.naver.client import LiveNaverClient, NaverApiError

SECRET = bcrypt.gensalt(rounds=4).decode()  # 네이버 client_secret 은 bcrypt salt 형식 ($2a$/$2b$)


def test_signature_is_bcrypt_of_id_timestamp():
    sig = make_signature("myclient", SECRET, 1643956077762)
    hashed = base64.standard_b64decode(sig)
    assert bcrypt.checkpw(b"myclient_1643956077762", hashed)
    url = make_signature("myclient", SECRET, 1643956077762, "urlsafe")
    assert base64.urlsafe_b64decode(url) == hashed


def test_token_manager_caches_and_refreshes():
    calls = []

    def fetch():
        calls.append(1)
        return f"tok{len(calls)}", 500 if len(calls) == 1 else 10800

    tm = TokenManager(fetch)
    assert tm.get() == "tok1"
    # 남은 시간 < 10분 → 재발급
    assert tm.get() == "tok2"
    assert tm.get() == "tok2"
    tm.invalidate()
    assert tm.get() == "tok3"


def _settings(**kw):
    base = dict(naver_mode="live", naver_client_id="cid", naver_client_secret=SECRET, naver_rps=1000)
    return Settings(**{**base, **kw})


def _client(handler, db=None, **kw):
    http = httpx.Client(base_url="https://api.commerce.naver.com/external", transport=httpx.MockTransport(handler))
    return LiveNaverClient(db, _settings(**kw), http=http)


def test_token_request_and_rate_limit_retry(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    seen = {"token": None, "orders": 0}

    def handler(req: httpx.Request):
        if req.url.path.endswith("/v1/oauth2/token"):
            form = dict(x.split("=", 1) for x in req.content.decode().split("&"))
            seen["token"] = form
            return httpx.Response(200, json={"access_token": "AT", "expires_in": 10800, "token_type": "Bearer"})
        if req.url.path.endswith("/last-changed-statuses"):
            seen["orders"] += 1
            assert req.headers["authorization"] == "Bearer AT"
            if seen["orders"] == 1:
                return httpx.Response(429, json={"code": "GW.RATE_LIMIT"})
            return httpx.Response(200, json={"data": {"lastChangeStatuses": [{"productOrderId": "1"}, {"productOrderId": "2"}]}})
        return httpx.Response(404)

    from datetime import datetime, timezone

    ids = _client(handler).fetch_changed_order_ids(datetime.now(timezone.utc))
    assert ids == ["1", "2"]
    assert seen["orders"] == 2
    t = seen["token"]
    assert t["grant_type"] == "client_credentials" and t["type"] == "SELF" and t["client_id"] == "cid"
    assert "client_secret_sign" in t and t["timestamp"].isdigit()


def test_mutations_are_dry_run_when_gate_closed(db):
    def handler(req):
        if req.url.path.endswith("/v1/oauth2/token"):
            return httpx.Response(200, json={"access_token": "AT", "expires_in": 10800})
        raise AssertionError(f"실제 호출 금지: {req.method} {req.url.path}")

    c = _client(handler, db=db, allow_public_listing=False, allow_naver_order_actions=False)
    res = c.create_product({"originProduct": {"name": "x"}}, "K:1")
    assert res["dryRun"] is True and res["id"].startswith("DRYRUN-")
    assert c.dispatch("123", "CJGLS", "1234567890")["dryRun"]
    assert c.confirm_orders(["123"])["dryRun"]
    assert c.upload_images(["https://a/b.jpg"]) == ["https://a/b.jpg"]
    db.flush()
    logs = db.query(ApiCallLog).filter_by(dry_run=True).all()
    assert {l.action for l in logs} >= {"create_product", "dispatch", "confirm", "image_upload"}


def test_mutation_sent_when_gate_open_and_errors_logged(db):
    def handler(req):
        if req.url.path.endswith("/v1/oauth2/token"):
            return httpx.Response(200, json={"access_token": "AT", "expires_in": 10800})
        if req.url.path.endswith("/v2/products"):
            body = json.loads(req.content)
            if body["originProduct"]["name"] == "bad":
                return httpx.Response(400, json={"code": "BAD_REQUEST", "message": "invalid", "invalidInputs": []})
            return httpx.Response(200, json={"originProductNo": 111, "smartstoreChannelProductNo": 222})
        return httpx.Response(404)

    c = _client(handler, db=db, allow_public_listing=True)
    assert c.create_product({"originProduct": {"name": "ok"}}, "K:1")["originProductNo"] == 111
    with pytest.raises(NaverApiError) as e:
        c.create_product({"originProduct": {"name": "bad"}}, "K:2")
    assert e.value.status == 400 and not e.value.retryable
    db.flush()
    failed = db.query(ApiCallLog).filter_by(success=False).one()
    assert failed.entity_id == "K:2" and failed.response["code"] == "BAD_REQUEST"


def test_carrier_mapping():
    assert map_carrier("CJ") == "CJGLS"
    assert map_carrier("우체국택배") == "EPOST"
    assert map_carrier("UNKNOWN") is None
    assert map_carrier("FOO", {"FOO": "BAR"}) == "BAR"
