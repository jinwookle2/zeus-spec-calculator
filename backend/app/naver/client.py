"""네이버 커머스 API 클라이언트.

- NaverClient: 공통 인터페이스
- LiveNaverClient: 실제 API. 변경(쓰기) 호출은 안전 스위치가 꺼져 있으면 Dry-run 으로 기록만 한다.
- MockNaverClient: 외부 호출 없이 동작 (NAVER_MODE=mock).

엔드포인트 출처: 네이버 커머스API 공식 문서 v2.91.0 (2026-10-28, apicenter.commerce.naver.com) 에서 전부 확인.
"""
from __future__ import annotations

import hashlib
import threading
from decimal import Decimal
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.logging_setup import log
from app.models import ApiCallLog, MockNaverOrder, utcnow
from app.naver.auth import TokenManager, make_signature

EP = {
    "token": ("POST", "/v1/oauth2/token"),
    "create_product": ("POST", "/v2/products"),
    "origin_product": ("GET", "/v2/products/origin-products/{no}"),
    "update_origin_product": ("PUT", "/v2/products/origin-products/{no}"),
    "change_status": ("PUT", "/v1/products/origin-products/{no}/change-status"),
    "image_upload": ("POST", "/v1/product-images/upload"),
    "categories": ("GET", "/v1/categories"),
    "restricted_tags": ("GET", "/v2/tags/restricted-tags"),
    "last_changed": ("GET", "/v1/pay-order/seller/product-orders/last-changed-statuses"),
    "order_query": ("POST", "/v1/pay-order/seller/product-orders/query"),
    "confirm": ("POST", "/v1/pay-order/seller/product-orders/confirm"),
    "dispatch": ("POST", "/v1/pay-order/seller/product-orders/dispatch"),
    "cancel_approve": ("POST", "/v1/pay-order/seller/product-orders/{id}/claim/cancel/approve"),
    "return_approve": ("POST", "/v1/pay-order/seller/product-orders/{id}/claim/return/approve"),
    # 참고(미사용): 옵션 재고/가격 변경 PUT /v1/products/origin-products/{no}/option-stock
    #   body: productSalePrice{salePrice}, optionInfo{optionCombinations[{id, stockQuantity, ...}]}
    "option_stock": ("PUT", "/v1/products/origin-products/{no}/option-stock"),
    "exchange_collect": ("POST", "/v1/pay-order/seller/product-orders/{id}/claim/exchange/collect/approve"),
    "exchange_dispatch": ("POST", "/v1/pay-order/seller/product-orders/{id}/claim/exchange/dispatch"),
    "settle_case": ("GET", "/v1/pay-settle/settle/case"),
}


class NaverApiError(Exception):
    def __init__(self, message: str, status: int | None = None, body: Any = None, retryable: bool = False):
        super().__init__(message)
        self.status, self.body, self.retryable = status, body, retryable


class SafetyGateClosed(Exception):
    """안전 스위치가 꺼져 실제 호출을 하지 않음 (Dry-run 결과 반환에 사용)."""


def _log_call(db: Session | None, action: str, request: Any, response: Any, success: bool,
              dry_run: bool = False, error: str | None = None, entity: str | None = None,
              entity_id: str | None = None) -> None:
    if db is None:
        return
    db.add(ApiCallLog(target="naver", action=action, request=_trim(request), response=_trim(response),
                      success=success, dry_run=dry_run, error=error, entity=entity, entity_id=entity_id))


def _trim(obj: Any) -> Any:
    """로그 저장 전 큰 HTML 축약 + 개인정보 키 제거."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in {"name", "tel1", "tel2", "baseAddress", "detailedAddress", "ordererName", "ordererTel"} and isinstance(v, str):
                out[k] = "***"
            elif k == "detailContent" and isinstance(v, str) and len(v) > 500:
                out[k] = v[:500] + "…(truncated)"
            else:
                out[k] = _trim(v)
        return out
    if isinstance(obj, list):
        return [_trim(v) for v in obj[:50]]
    return obj


class NaverClient(ABC):
    mode: str

    def __init__(self, db: Session | None = None, settings: Settings | None = None):
        self.db = db
        self.s = settings or get_settings()

    @abstractmethod
    def upload_images(self, urls: list[str]) -> list[str]: ...
    @abstractmethod
    def get_categories(self) -> list[dict]: ...
    @abstractmethod
    def create_product(self, payload: dict, listing_key: str) -> dict: ...
    @abstractmethod
    def get_origin_product(self, origin_no: str) -> dict: ...
    @abstractmethod
    def update_origin_product(self, origin_no: str, payload: dict) -> dict: ...
    @abstractmethod
    def change_status(self, origin_no: str, status: str, stock: int | None = None) -> dict: ...
    @abstractmethod
    def fetch_changed_order_ids(self, since: datetime) -> list[str]: ...
    @abstractmethod
    def get_product_orders(self, ids: list[str]) -> list[dict]: ...
    @abstractmethod
    def confirm_orders(self, ids: list[str]) -> dict: ...
    @abstractmethod
    def dispatch(self, product_order_id: str, carrier: str, tracking_no: str) -> dict: ...
    @abstractmethod
    def approve_claim(self, product_order_id: str, claim: str) -> dict: ...
    @abstractmethod
    def check_restricted_tags(self, tags: list[str]) -> set[str]: ...
    @abstractmethod
    def approve_exchange_collect(self, product_order_id: str) -> dict: ...
    @abstractmethod
    def redispatch_exchange(self, product_order_id: str, carrier: str, tracking_no: str) -> dict: ...
    @abstractmethod
    def get_settlements(self, search_date: str, page: int = 1) -> tuple[list[dict], int]:
        """건별 정산 내역 (정산 기준일). 반환: (elements, totalPages)"""

    # 공통 헬퍼: 가격/재고 변경은 원상품 조회 → 수정 (공식 엔드포인트만 사용)
    def update_price_stock(self, origin_no: str, sale_price: int | None = None, stock: int | None = None) -> dict:
        current = self.get_origin_product(origin_no)
        op = current.get("originProduct", {})
        if sale_price is not None:
            op["salePrice"] = sale_price
        if stock is not None:
            op["stockQuantity"] = stock
        return self.update_origin_product(origin_no, {"originProduct": op,
                                                       "smartstoreChannelProduct": current.get("smartstoreChannelProduct", {})})


# --------------------------------------------------------------------------- Live


class _RateLimiter:
    def __init__(self, rps: float):
        self.interval = 1.0 / rps if rps > 0 else 0
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self.interval
        if delay > 0:
            time.sleep(delay)


class LiveNaverClient(NaverClient):
    mode = "live"
    _limiters: dict[str, _RateLimiter] = {}

    def __init__(self, db: Session | None = None, settings: Settings | None = None,
                 http: httpx.Client | None = None):
        super().__init__(db, settings)
        if not self.s.naver_client_id or not self.s.naver_client_secret:
            raise NaverApiError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 미설정")
        self.http = http or httpx.Client(base_url=self.s.naver_base_url, timeout=30)
        self.tokens = TokenManager(self._fetch_token)
        self.limiter = self._limiters.setdefault(self.s.naver_client_id, _RateLimiter(self.s.naver_rps))

    def _fetch_token(self) -> tuple[str, int]:
        ts = int(time.time() * 1000)
        params = {
            "client_id": self.s.naver_client_id,
            "timestamp": ts,
            "client_secret_sign": make_signature(self.s.naver_client_id, self.s.naver_client_secret, ts,
                                                 self.s.naver_sign_b64),
            "grant_type": "client_credentials",
            "type": self.s.naver_token_type,
        }
        if self.s.naver_token_type == "SELLER":
            params["account_id"] = self.s.naver_account_id
        resp = self.http.post(EP["token"][1], data=params)
        if resp.status_code != 200:
            raise NaverApiError(f"토큰 발급 실패 {resp.status_code}", resp.status_code, _safe_json(resp))
        body = resp.json()
        return body["access_token"], int(body.get("expires_in", 10800))

    def _request(self, key: str, *, path_args: dict | None = None, retries: int = 3, **kw) -> Any:
        method, path = EP[key]
        path = path.format(**(path_args or {}))
        for attempt in range(retries + 1):
            self.limiter.wait()
            headers = {"Authorization": f"Bearer {self.tokens.get()}", **kw.pop("headers", {})}
            try:
                resp = self.http.request(method, path, headers=headers, **kw)
            except httpx.TransportError as e:
                if attempt < retries:
                    time.sleep(2 ** attempt)
                    continue
                raise NaverApiError(f"네트워크 오류: {e}", retryable=True) from e
            if resp.status_code == 401 and attempt < retries:
                self.tokens.invalidate()
                continue
            if resp.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(min(2 ** attempt, 10))
                continue
            if resp.status_code >= 400:
                body = _safe_json(resp)
                raise NaverApiError(f"{key} 실패 {resp.status_code}: {body}", resp.status_code, body,
                                    retryable=resp.status_code in (429, 500, 502, 503, 504))
            return _safe_json(resp)
        raise NaverApiError(f"{key} 재시도 초과", retryable=True)

    def _mutation(self, key: str, gate: bool, gate_name: str, request: dict, entity_id: str | None = None,
                  **kw) -> dict:
        if not gate:
            fake = {"dryRun": True, "id": "DRYRUN-" + hashlib.sha1(repr(request).encode()).hexdigest()[:10]}
            _log_call(self.db, key, request, fake, True, dry_run=True, entity_id=entity_id,
                      error=f"{gate_name}=false → 실제 호출 안 함")
            return fake
        try:
            res = self._request(key, **kw)
            _log_call(self.db, key, request, res, True, entity_id=entity_id)
            return res
        except NaverApiError as e:
            _log_call(self.db, key, request, e.body, False, error=str(e), entity_id=entity_id)
            raise

    # -- 읽기 --
    def get_categories(self) -> list[dict]:
        return self._request("categories")

    def get_origin_product(self, origin_no: str) -> dict:
        return self._request("origin_product", path_args={"no": origin_no})

    def fetch_changed_order_ids(self, since: datetime) -> list[str]:
        """변경 상품 주문 조회. lastChangedTo 생략 시 24시간 범위만 조회되므로(공식 문서)
        since ~ 현재를 24시간 창으로 나눠 조회하고, 창 안에서는 more(moreFrom/moreSequence)로 페이지를 넘긴다."""
        from datetime import timedelta

        def fmt(dt: datetime) -> str:
            return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds")

        ids: list[str] = []
        now = datetime.now(timezone.utc)
        start = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
        while start < now:
            end = min(start + timedelta(hours=24), now)
            params: dict[str, Any] = {"lastChangedFrom": fmt(start), "lastChangedTo": fmt(end)}
            for _ in range(100):
                body = self._request("last_changed", params=params) or {}
                data = body.get("data", {})
                ids += [x["productOrderId"] for x in data.get("lastChangeStatuses", [])]
                more = data.get("more")
                if not more:
                    break
                params = {"lastChangedFrom": more["moreFrom"], "lastChangedTo": fmt(end),
                          "moreSequence": more["moreSequence"]}
            start = end
        return list(dict.fromkeys(ids))

    def get_product_orders(self, ids: list[str]) -> list[dict]:
        out: list[dict] = []
        for i in range(0, len(ids), 300):
            body = self._request("order_query", json={"productOrderIds": ids[i:i + 300]}) or {}
            out += body.get("data", [])
        return out

    # -- 쓰기 (안전 스위치) --
    def upload_images(self, urls: list[str]) -> list[str]:
        if not self.s.allow_public_listing:
            _log_call(self.db, "image_upload", {"urls": urls}, None, True, dry_run=True,
                      error="ALLOW_PUBLIC_LISTING=false → 업로드 생략")
            return urls
        files = []
        for i, u in enumerate(urls[:10]):
            r = httpx.get(u, timeout=20, follow_redirects=True)
            r.raise_for_status()
            files.append(("imageFiles", (f"img{i}.jpg", r.content, r.headers.get("content-type", "image/jpeg"))))
        body = self._request("image_upload", files=files)
        return [img["url"] for img in body.get("images", [])]

    def create_product(self, payload: dict, listing_key: str) -> dict:
        return self._mutation("create_product", self.s.allow_public_listing, "ALLOW_PUBLIC_LISTING", payload,
                              entity_id=listing_key, json=payload)

    def update_origin_product(self, origin_no: str, payload: dict) -> dict:
        return self._mutation("update_origin_product", self.s.allow_public_listing, "ALLOW_PUBLIC_LISTING", payload,
                              entity_id=origin_no, path_args={"no": origin_no}, json=payload)

    def change_status(self, origin_no: str, status: str, stock: int | None = None) -> dict:
        body = {"statusType": status}
        if stock is not None:
            body["stockQuantity"] = stock
        return self._mutation("change_status", self.s.allow_public_listing, "ALLOW_PUBLIC_LISTING", body,
                              entity_id=origin_no, path_args={"no": origin_no}, json=body)

    def update_price_stock(self, origin_no: str, sale_price: int | None = None, stock: int | None = None) -> dict:
        if not self.s.allow_public_listing:
            return self._mutation("update_origin_product", False, "ALLOW_PUBLIC_LISTING",
                                  {"salePrice": sale_price, "stockQuantity": stock}, entity_id=origin_no)
        return super().update_price_stock(origin_no, sale_price, stock)

    def confirm_orders(self, ids: list[str]) -> dict:
        body = {"productOrderIds": ids}
        return self._mutation("confirm", self.s.allow_naver_order_actions, "ALLOW_NAVER_ORDER_ACTIONS", body, json=body)

    def dispatch(self, product_order_id: str, carrier: str, tracking_no: str) -> dict:
        body = {"dispatchProductOrders": [{
            "productOrderId": product_order_id, "deliveryMethod": "DELIVERY", "deliveryCompanyCode": carrier,
            "trackingNumber": tracking_no, "dispatchDate": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        }]}
        return self._mutation("dispatch", self.s.allow_naver_order_actions, "ALLOW_NAVER_ORDER_ACTIONS", body,
                              entity_id=product_order_id, json=body)

    def approve_claim(self, product_order_id: str, claim: str) -> dict:
        key = {"CANCEL": "cancel_approve", "RETURN": "return_approve"}[claim]
        return self._mutation(key, self.s.allow_naver_order_actions, "ALLOW_NAVER_ORDER_ACTIONS",
                              {"productOrderId": product_order_id}, entity_id=product_order_id,
                              path_args={"id": product_order_id})

    def check_restricted_tags(self, tags: list[str]) -> set[str]:
        if not tags:
            return set()
        body = self._request("restricted_tags", params=[("tags", t) for t in tags]) or []
        if not isinstance(body, list):
            raise NaverApiError(f"restricted_tags 응답 형식 오류: {str(body)[:200]}")
        return {x["tag"] for x in body if x.get("restricted")}

    def approve_exchange_collect(self, product_order_id: str) -> dict:
        return self._mutation("exchange_collect", self.s.allow_naver_order_actions, "ALLOW_NAVER_ORDER_ACTIONS",
                              {"productOrderId": product_order_id}, entity_id=product_order_id,
                              path_args={"id": product_order_id})

    def redispatch_exchange(self, product_order_id: str, carrier: str, tracking_no: str) -> dict:
        body = {"reDeliveryMethod": "DELIVERY", "reDeliveryCompany": carrier, "reDeliveryTrackingNumber": tracking_no}
        return self._mutation("exchange_dispatch", self.s.allow_naver_order_actions, "ALLOW_NAVER_ORDER_ACTIONS", body,
                              entity_id=product_order_id, path_args={"id": product_order_id}, json=body)

    def get_settlements(self, search_date: str, page: int = 1) -> tuple[list[dict], int]:
        body = self._request("settle_case", params={
            "searchDate": search_date, "periodType": "SETTLE_CASEBYCASE_SETTLE_BASIS_DATE",
            "pageNumber": page, "pageSize": 1000}) or {}
        return body.get("elements", []), int((body.get("pagination") or {}).get("totalPages") or 1)


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return {"text": resp.text[:1000]}


# --------------------------------------------------------------------------- Mock


class MockNaverClient(NaverClient):
    """외부 호출 없음. 상품은 결정적 번호를 발급하고, 주문은 mock_naver_orders 테이블에서 읽는다."""

    mode = "mock"
    fail_listing_keys: set[str] = set()  # 테스트에서 등록 실패 주입

    def upload_images(self, urls: list[str]) -> list[str]:
        return [f"https://shop-phinf.pstatic.net/mock/{hashlib.md5(u.encode()).hexdigest()[:12]}.jpg" for u in urls]

    def get_categories(self) -> list[dict]:
        from app.services.ai_processor import MOCK_CATEGORIES

        return [{"id": cid, "wholeCategoryName": name, "last": True} for name, cid in MOCK_CATEGORIES.items()]

    def create_product(self, payload: dict, listing_key: str) -> dict:
        if listing_key in self.fail_listing_keys:
            err = {"code": "BAD_REQUEST", "message": "mock: 필수 고시정보 누락",
                   "invalidInputs": [{"name": "productInfoProvidedNotice", "message": "필수값"}]}
            _log_call(self.db, "create_product", payload, err, False, error=err["message"], entity_id=listing_key)
            raise NaverApiError("create_product 실패 400", 400, err)
        n = int(hashlib.sha1(listing_key.encode()).hexdigest()[:8], 16)
        res = {"originProductNo": str(10_000_000 + n % 89_999_999), "smartstoreChannelProductNo": str(20_000_000 + n % 79_999_999)}
        _log_call(self.db, "create_product", payload, res, True, entity_id=listing_key)
        return res

    def get_origin_product(self, origin_no: str) -> dict:
        return {"originProduct": {"originProductNo": origin_no}}

    def update_origin_product(self, origin_no: str, payload: dict) -> dict:
        _log_call(self.db, "update_origin_product", payload, {"ok": True}, True, entity_id=origin_no)
        return {"ok": True}

    def change_status(self, origin_no: str, status: str, stock: int | None = None) -> dict:
        _log_call(self.db, "change_status", {"statusType": status, "stockQuantity": stock}, {"ok": True}, True,
                  entity_id=origin_no)
        return {"ok": True}

    def fetch_changed_order_ids(self, since: datetime) -> list[str]:
        assert self.db is not None
        rows = self.db.query(MockNaverOrder).all()
        return [r.product_order_id for r in rows if _aware(r.changed_at) >= _aware(since)]

    def get_product_orders(self, ids: list[str]) -> list[dict]:
        assert self.db is not None
        rows = self.db.query(MockNaverOrder).filter(MockNaverOrder.product_order_id.in_(ids)).all()
        return [r.payload | {"productOrder": {**r.payload.get("productOrder", {}), "productOrderStatus": r.status}}
                for r in rows]

    def confirm_orders(self, ids: list[str]) -> dict:
        _log_call(self.db, "confirm", {"productOrderIds": ids}, {"ok": True}, True)
        return {"ok": True}

    def dispatch(self, product_order_id: str, carrier: str, tracking_no: str) -> dict:
        assert self.db is not None
        row = self.db.query(MockNaverOrder).filter_by(product_order_id=product_order_id).one_or_none()
        if row:
            row.status = "DELIVERING"
            row.changed_at = utcnow()
        _log_call(self.db, "dispatch", {"productOrderId": product_order_id, "deliveryCompanyCode": carrier,
                                        "trackingNumber": tracking_no}, {"ok": True}, True, entity_id=product_order_id)
        return {"ok": True}

    def approve_claim(self, product_order_id: str, claim: str) -> dict:
        _log_call(self.db, f"{claim.lower()}_approve", {"productOrderId": product_order_id}, {"ok": True}, True,
                  entity_id=product_order_id)
        return {"ok": True}

    restricted_tags: set[str] = {"최저가", "무료배송", "특가", "정품", "명품", "나이키", "할인"}
    actual_fee_rates = (Decimal("0.0363"), Decimal("0.02"))  # Mock 실제 수수료 (주문관리 + 판매연동)

    def check_restricted_tags(self, tags: list[str]) -> set[str]:
        return {t for t in tags if t in self.restricted_tags}

    def approve_exchange_collect(self, product_order_id: str) -> dict:
        _log_call(self.db, "exchange_collect", {"productOrderId": product_order_id}, {"ok": True}, True,
                  entity_id=product_order_id)
        return {"ok": True}

    def redispatch_exchange(self, product_order_id: str, carrier: str, tracking_no: str) -> dict:
        _log_call(self.db, "exchange_dispatch", {"productOrderId": product_order_id, "reDeliveryCompany": carrier,
                                                 "reDeliveryTrackingNumber": tracking_no}, {"ok": True}, True,
                  entity_id=product_order_id)
        return {"ok": True}

    def get_settlements(self, search_date: str, page: int = 1) -> tuple[list[dict], int]:
        """배송 이후 단계의 Mock 주문에 대해 변경일 = 정산 기준일 로 정산 내역을 만든다."""
        assert self.db is not None
        out = []
        for r in self.db.query(MockNaverOrder).filter(
                MockNaverOrder.status.in_(["DELIVERING", "DELIVERED", "PURCHASE_DECIDED"])).all():
            if _aware(r.changed_at).date().isoformat() != search_date:
                continue
            po = r.payload["productOrder"]
            amount = Decimal(str(po["totalPaymentAmount"]))
            pay_fee = (amount * self.actual_fee_rates[0]).quantize(Decimal("1"))
            link_fee = (amount * self.actual_fee_rates[1]).quantize(Decimal("1"))
            out.append({
                "settleBasisDate": search_date, "settleExpectDate": search_date, "orderId": r.order_id,
                "productOrderId": r.product_order_id, "productOrderType": "PROD_ORDER", "settleType": "NORMAL_SETTLE_ORIGINAL",
                "paySettleAmount": int(amount), "totalPayCommissionAmount": -int(pay_fee),
                "freeInstallmentCommissionAmount": 0, "sellingInterlockCommissionAmount": -int(link_fee),
                "benefitSettleAmount": 0, "settleExpectAmount": int(amount - pay_fee - link_fee),
            })
        return out, 1


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def get_naver_client(db: Session | None = None) -> NaverClient:
    s = get_settings()
    if s.naver_mode == "live":
        log.info("naver.client", mode="live", public_listing=s.allow_public_listing,
                 order_actions=s.allow_naver_order_actions)
        return LiveNaverClient(db, s)
    return MockNaverClient(db, s)
