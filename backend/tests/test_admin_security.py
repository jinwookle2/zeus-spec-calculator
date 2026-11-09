"""2단계 인증, 사용자 관리, 공급사 반품 접수."""
import time

from app.models import Order, OrderStatus, Product, PurchaseOrder
from app.security import totp_code, verify_totp


def test_totp_rfc6238_vector():
    # RFC 6238 부록 B (SHA1, secret "12345678901234567890"), T=59 → 94287082 (8자리)의 하위 6자리
    import base64

    secret = base64.b32encode(b"12345678901234567890").decode()
    assert totp_code(secret, 59, digits=8) == "94287082"
    assert totp_code(secret, 1111111109, digits=8) == "07081804"
    assert verify_totp(secret, totp_code(secret)) and not verify_totp(secret, "000000x")


def test_2fa_enable_login_disable(client, admin_h):
    r = client.post("/api/auth/2fa/setup", headers=admin_h)
    secret = r.json()["secret"]
    assert r.json()["otpauth_uri"].startswith("otpauth://totp/")
    assert client.post("/api/auth/2fa/enable", json={"code": "000000"}, headers=admin_h).status_code == 400
    assert client.post("/api/auth/2fa/enable", json={"code": totp_code(secret)}, headers=admin_h).status_code == 200
    assert client.get("/api/auth/me", headers=admin_h).json()["totp_enabled"] is True
    # 비밀번호만으로는 로그인 불가
    r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin1234!"})
    assert r.status_code == 401 and r.json()["detail"] == "OTP_REQUIRED"
    r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin1234!", "otp": "123456"})
    assert r.status_code == 401 and r.json()["detail"] != "OTP_REQUIRED"
    r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin1234!", "otp": totp_code(secret)})
    assert r.status_code == 200
    # 비밀번호가 틀리면 OTP 여부를 알려주지 않음
    r = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "nope"})
    assert r.json()["detail"] != "OTP_REQUIRED"
    assert client.post("/api/auth/2fa/disable", json={"password": "admin1234!", "code": totp_code(secret)}, headers=admin_h).status_code == 200
    assert client.post("/api/auth/login", json={"email": "admin@example.com", "password": "admin1234!"}).status_code == 200


def test_user_management(client, admin_h, op_h):
    users = client.get("/api/users", headers=admin_h).json()
    assert all("password_hash" not in u and "totp_secret_enc" not in u for u in users)
    assert client.get("/api/users", headers=op_h).status_code == 403
    r = client.post("/api/users", json={"email": "new@example.com", "password": "newuser12345", "role": "viewer"}, headers=admin_h)
    uid = r.json()["id"]
    assert client.patch(f"/api/users/{uid}", json={"role": "operator"}, headers=admin_h).json()["role"] == "operator"
    # 잠금 해제
    for _ in range(5):
        client.post("/api/auth/login", json={"email": "new@example.com", "password": "bad"})
    assert client.post("/api/auth/login", json={"email": "new@example.com", "password": "newuser12345"}).status_code == 429
    client.patch(f"/api/users/{uid}", json={"unlock": True}, headers=admin_h)
    assert client.post("/api/auth/login", json={"email": "new@example.com", "password": "newuser12345"}).status_code == 200
    # 비활성화
    client.patch(f"/api/users/{uid}", json={"active": False}, headers=admin_h)
    assert client.post("/api/auth/login", json={"email": "new@example.com", "password": "newuser12345"}).status_code == 401
    # 자기 자신 강등 금지
    me_id = next(u["id"] for u in users if u["email"] == "admin@example.com")
    assert client.patch(f"/api/users/{me_id}", json={"role": "viewer"}, headers=admin_h).status_code == 409


def test_return_request_creates_supplier_return(client, op_h, db):
    def run(j):
        assert client.post(f"/api/jobs/{j}/run", headers=op_h).status_code == 200

    for j in ("source_products", "process_candidates", "publish_listings"):
        run(j)
    p = db.query(Product).filter_by(listing_key="MOCKA:MA-1001").one()
    poid = client.post("/api/mock/orders", json={"product_id": p.id}, headers=op_h).json()["product_order_id"]
    for j in ("collect_orders", "process_orders", "poll_shipments"):
        run(j)
    client.post(f"/api/mock/orders/{poid}/status", json={"status": "DELIVERING", "claim_type": "RETURN"}, headers=op_h)
    run("collect_orders")
    db.expire_all()
    order = db.query(Order).filter_by(naver_product_order_id=poid).one()
    po = db.query(PurchaseOrder).filter_by(order_id=order.id).one()
    assert order.status == OrderStatus.RETURN_REQUESTED
    assert po.return_status == "REQUESTED" and po.supplier_return_no.startswith("RET-")
    assert client.post(f"/api/orders/{order.id}/approve-return", headers=op_h).status_code == 200
    db.expire_all()
    assert db.get(Order, order.id).status == OrderStatus.RETURNED
