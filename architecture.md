# 아키텍처: 네이버 스마트스토어 위탁판매 자동화

## 1. 구성

```
                ┌──────────────── 관리자 (Next.js + Tailwind, :3000) ────────────────┐
                │ 대시보드 · 공급사 · 소싱 · 등록대기 · 등록상품 · 가격 · 재고 · 주문   │
                │ 발주 · 배송 · 매출분석 · 오류/알림 · 자동화설정 · API연결            │
                └──────────────────────────────┬────────────────────────────────────┘
                                               │ /api (Next rewrite → FastAPI)
┌────────────┐  X-Service-Token  ┌─────────────▼─────────────┐      ┌───────────────┐
│ n8n (선택) ├──────────────────►│ FastAPI (:8000)           │◄────►│ PostgreSQL 16 │
└────────────┘                   │  JWT + 역할(admin/operator│      └───────────────┘
                                 │  /viewer), 감사로그        │
┌────────────┐   tick(60s)       │  services/* (도메인 로직)  │      ┌───────────────┐
│ Celery beat├──► Redis ◄────────┤  jobs.py (작업 단위)       │◄────►│ Redis (큐/락) │
└────────────┘        │          └─────────────┬─────────────┘      └───────────────┘
              ┌───────▼───────┐                │
              │ Celery worker │──── 같은 jobs.py 실행 (재시도 · DLQ · Redis 락)
              └───────────────┘
                       │
     ┌─────────────────┼──────────────────────────────┬─────────────────────┐
     ▼                 ▼                              ▼                     ▼
 SupplierAdapter   NaverClient                   ClaudeProcessor      Alert webhook
 (mock/csv/api)    (Mock | Live + 안전스위치)    (규칙기반 폴백)       (Slack/n8n)
```

- **단일 도메인 계층**: `backend/app/services/*` 에 모든 업무 규칙이 있다. API, Celery, n8n 모두 `app/jobs.py` 의 같은 작업을 호출하므로 동작이 한 곳에서 정의된다.
- **스케줄**: Celery beat 는 1분마다 `jobs.tick` 만 실행하고, tick 이 DB 설정(등록 주기, 주문 수집 주기 등)과 마지막 실행 시각을 비교해 도래한 작업을 큐에 넣는다. 그래서 관리자 화면에서 주기를 바꾸면 재배포 없이 반영된다. 동일 작업의 동시 실행은 Redis 락으로 막는다.
- **n8n**: 선택 사항이다. 서비스 토큰으로 `/api/jobs/{name}/run` 을 호출하는 워크플로 예시와 장애 알림 중계 예시를 제공한다(`n8n/workflows`). Celery 와 함께 써도 Redis 락 덕분에 중복 실행되지 않는다(Celery 경유 시). n8n 만 쓸 경우 beat 를 끄면 된다.

## 2. 데이터 흐름

### 2.1 상품
```
공급사 Adapter.fetch_products()
  → SupplierProduct upsert (공급사ID+상품코드 유니크)
  → content_hash 로 중복 감지(공급사 간 포함) · 품절 · 단종 처리
  → 가공(ClaudeProcessor | RuleBasedProcessor): 상품명/카테고리/태그/상세HTML/옵션 표준화/고시정보
  → AI guardrail: 원본에 없는 브랜드·인증·원산지·소재·효능 표현 제거
  → compliance: 금지 키워드, 효능 표현, 브랜드 판매권한, 이미지 사용권, 고시정보 필수값, 재고
  → pricing: 목표 마진·최소 이익을 만족하는 최소 판매가, 시장가(권장소비자가) 초과 시 차단
  → Product.status = BLOCKED | PENDING_APPROVAL | APPROVED(검증·자동등록 허용 공급사 + 경고 없음)
  → publish: 일일 한도 내에서 이미지 업로드 → POST /v2/products → LISTED (실패 시 FAILED + 원인 기록)
  → sync_inventory: 재고 반영, 품절 처리/재개, 공급가 변동 시 재가격 또는 판매중지
```
중복 등록 방지 장치는 세 가지다. `listing_key = 공급사코드:상품코드` 유니크 제약, 이미 받은 `naver_origin_product_no` 가 있으면 건너뛰기, `sellerManagementCode=listing_key` 로 네이버 측에서도 상품을 식별한다.

### 2.2 주문 상태 머신 (`services/order_state.py`)
```
PAID → STOCK_CHECKED → PURCHASE_REQUESTED → SUPPLIER_CONFIRMED → SHIPPED → TRACKING_REGISTERED → DELIVERED
   예외: AWAITING_APPROVAL(발주 승인 대기), ON_HOLD(재고 불일치/한도/매핑 실패), FAILED(발주 재시도 소진),
         CANCEL_REQUESTED → CANCELLED, RETURN_REQUESTED → RETURNED, EXCHANGE_REQUESTED
```
- 허용되지 않은 전이는 예외로 막는다. 모든 전이는 `order_events` 에 기록한다(행위자, 사유, 시각).
- **중복 주문 방지**: `orders.naver_product_order_id` 유니크 제약.
- **중복 발주 방지**: `purchase_orders.order_id` 와 `idempotency_key`(=`PO-{상품주문번호}`) 유니크 제약. 이미 발주번호가 있으면 재호출하지 않고, 공급사에도 멱등키를 전달한다.
- **재시도**: 일시 오류(AdapterError)는 `REQUESTING` 상태로 남겨 `retry_purchases` 가 다시 시도한다. `max_purchase_retries` 를 넘기면 FAILED 처리하고 Dead Letter Queue 에 넣은 뒤 알림을 보낸다.
- **재고 불일치**: 주문 시 공급사 재고가 부족하거나 공급가가 허용치 이상 오르면 주문을 ON_HOLD 로 돌리고, 해당 공급사 자동 발주를 중단(`auto_purchase_paused`)한 뒤 알림을 보낸다. 재개는 관리자가 한다.
- **일일 발주 금액 한도**: 실제(live) 공급사 발주에 적용한다. 초과하면 ON_HOLD.

### 2.3 자동 발주 판정 (모두 충족해야 자동)
1. 전역 `auto_purchase_enabled`
2. 공급사 Adapter 가 발주 API 지원
3. 공급사 `verified` + `auto_purchase_allowed` + 자동 발주 중단 상태 아님
4. 실제 공급사이면 환경변수 `ALLOW_REAL_PURCHASE=true` (아니면 Dry-run 기록 후 승인 대기)

충족하지 못하면 `AWAITING_APPROVAL` 로 둔다. 관리자는 'API 발주 승인' 또는 '수동 발주 완료(발주번호 입력)'로 처리한다.

## 3. 안전 장치 (실제 외부 효과의 이중 잠금)

| 외부 효과 | 1차: 환경변수 (서버) | 2차: DB 설정/공급사 플래그 |
|---|---|---|
| 네이버 상품 공개 등록/수정/상태변경 | `NAVER_MODE=live` + `ALLOW_PUBLIC_LISTING` | 상품 승인(관리자 또는 검증 공급사 자동) |
| 네이버 발주확인/발송처리/클레임승인 | `ALLOW_NAVER_ORDER_ACTIONS` | — |
| 공급사 실제 발주/결제 | `ALLOW_REAL_PURCHASE` | 공급사 verified/auto_purchase_allowed, 일일 금액 한도 |
| 고객 개인정보 공급사 전송 | `ALLOW_PII_TRANSFER` | 공급사 `pii_transfer_agreed` (계약) |

스위치가 꺼져 있으면 `LiveNaverClient` 는 HTTP 요청을 보내지 않는다. 대신 요청 본문을 `api_call_logs(dry_run=true)` 에 남기고 `DRYRUN-…` 결과를 돌려준다. 그래서 실제 계정을 연결한 상태에서도 요청 형식을 검증할 수 있다. 이 동작은 `tests/test_live_gates.py` 로 확인한다.

## 4. 보안
- 비밀값(네이버, Claude, JWT, 서비스 토큰, PII 키)은 환경변수/Secret Manager 로만 주입한다. DB 와 화면에는 저장하거나 표시하지 않는다.
- 개인정보(수령인 이름, 전화, 주소)는 Fernet 으로 암호화해 저장한다. API 응답은 기본 마스킹하고, `?reveal=true` 는 admin 만 쓸 수 있으며 감사 로그에 남는다. 외부 API 로그에서도 PII 키는 마스킹한다.
- 역할: viewer(조회) < operator(승인, 발주, 송장, 작업 실행) < admin(설정, 공급사, 사용자, 개인정보 열람, 감사 로그).
- 운영 환경에서 기본 JWT_SECRET/SERVICE_TOKEN 을 쓰면 서버가 기동을 거부한다. 운영에서 PII 키가 없으면 암호화가 실패한다.
- API 호출 제한: 클라이언트 ID별 RPS 제한기(`NAVER_RPS`)를 둔다. 429/5xx 는 지수 백오프로 재시도하고, 401 은 토큰을 재발급해 재시도한다.

## 5. 모니터링
- structlog JSON 구조화 로그, Sentry(`SENTRY_DSN`, `send_default_pii=False`).
- `alerts` 테이블과 `ALERT_WEBHOOK_URL`(warning 이상 푸시), `job_runs`(작업별 결과), `dead_letters`, `api_call_logs`, `audit_logs`, `order_events`.

## 6. DB 테이블
`users`, `suppliers`, `supplier_products`, `products`, `orders`, `order_events`, `purchase_orders`, `app_settings`, `audit_logs`, `alerts`, `dead_letters`, `job_runs`, `api_call_logs`, `naver_categories`, `settlements`, `mock_naver_orders`(mock 전용).
스키마는 Alembic(`backend/migrations`)으로 관리한다. API 가 시작될 때 `alembic upgrade head` 를 실행하고(`DB_AUTO_MIGRATE=true`), 워커와 비트는 API 가 healthy 가 된 뒤 시작한다. 모델을 바꾸면 `alembic revision --autogenerate` 로 새 revision 을 만든다. `tests/test_migrations.py` 가 revision 누락을 잡아낸다.

## 8. 운영 보조 기능
- **카테고리 동기화** (`sync_categories`, 하루 1회): `GET /v1/categories` 결과를 `naver_categories` 에 저장하고, 상품 가공 시 리프 카테고리 추천에 쓴다. Claude 에는 규칙 점수 상위 15개 후보만 주며, 후보 밖의 답은 버린다. 동기화 전에는 Mock 사전을 쓴다.
- **제한 태그 필터**: 등록 직전에 `GET /v2/tags/restricted-tags` 로 조회(읽기 전용)해서 제한 태그를 빼고 경고로 남긴다.
- **교환 처리**: 교환 요청이 오면 `EXCHANGE_REQUESTED` 와 알림 → 관리자가 '교환 수거 완료'(`claim/exchange/collect/approve`) → 재배송 송장 등록(`claim/exchange/dispatch`, 택배사 공식 코드 매핑) → `TRACKING_REGISTERED`. 공급사에 재배송을 요청하는 일은 수동이다.
- **정산 대사** (`reconcile_settlements`, 6시간마다, 최근 7일): `GET /v1/pay-settle/settle/case` 로 건별 정산을 저장해 주문과 연결한다. 실제 수수료(결제+판매연동+무이자)와 설정 수수료율로 계산한 추정치의 차이가 max(100원, 0.5%) 를 넘으면 불일치로 표시하고 알림을 보낸다. 매출 분석은 정산된 주문에 한해 실제 수수료를 쓴다.
- **관리자 보안**: 로그인 5회 실패 시 15분 잠금, 비밀번호 변경(10자 이상), 2단계 인증(TOTP, 비밀키는 Fernet 암호화 저장), admin 의 사용자 관리. 잠금·변경·2FA 설정은 감사 로그에 기록. 초기 비밀번호로 로그인하면 변경을 권고한다.
- **반품**: 네이버 반품 요청이 오면 공급사 Adapter 의 `request_return` 으로 반품을 접수하고 접수번호를 발주에 저장한다. API 가 없으면 `MANUAL_REQUIRED` 로 표시하고 알림을 보낸다.
- **CI**: `.github/workflows/ci.yml` 이 마이그레이션 검사, 백엔드 테스트(SQLite/PostgreSQL), 프론트 빌드, E2E(PostgreSQL+Redis+Celery+Next) 를 실행한다.

## 7. 네이버 Commerce API 근거

출처: 공식 문서 **v2.91.0 (2026-10-28)** (apicenter.commerce.naver.com/docs/commerce-api/current). 2026-11-05 에 페이지별로 확인했다.

| 기능 | 메서드 · 경로 |
|---|---|
| 인증 토큰 발급 | `POST /v1/oauth2/token` (client_id, timestamp(ms), client_secret_sign, grant_type=client_credentials, type=SELF\|SELLER). 서명 = base64(bcrypt(`client_id_timestamp`, salt=client_secret)), 유효 3시간 |
| 상품 이미지 다건 등록 | `POST /v1/product-images/upload` |
| 전체 카테고리 조회 | `GET /v1/categories` |
| 원산지 코드 전체 조회 | `GET /v1/product-origin-areas` |
| 상품정보제공고시 상품군 | `GET /v1/products-for-provided-notice` |
| (v2) 제한 태그 여부 | `GET /v2/tags/restricted-tags` |
| (v2) 상품 등록 | `POST /v2/products` |
| (v2) 원상품 조회 / 수정 | `GET` · `PUT /v2/products/origin-products/{originProductNo}` |
| 판매상태 변경 | `PUT /v1/products/origin-products/{originProductNo}/change-status` |
| 옵션 재고·가격 변경 | `PUT /v1/products/origin-products/{originProductNo}/option-stock` (참고, 현재 미사용) |
| 변경 상품 주문 조회 | `GET /v1/pay-order/seller/product-orders/last-changed-statuses` (lastChangedFrom 필수, lastChangedTo 생략 시 24시간, 최대 300건, `more.moreFrom/moreSequence` 로 이어받기) |
| 상품 주문 상세 | `POST /v1/pay-order/seller/product-orders/query` (productOrderIds) |
| 발주 확인 | `POST /v1/pay-order/seller/product-orders/confirm` |
| 발송 처리 | `POST /v1/pay-order/seller/product-orders/dispatch` (dispatchProductOrders[productOrderId, deliveryMethod, deliveryCompanyCode, trackingNumber, dispatchDate]) |
| 취소 승인 / 반품 승인 | `POST /v1/pay-order/seller/product-orders/{productOrderId}/claim/cancel/approve` · `/claim/return/approve` |
| 교환 수거완료 / 재배송 | `.../claim/exchange/collect/approve` · `.../claim/exchange/dispatch` |
| 정산 (건별/일별) | `GET /v1/pay-settle/settle/case` · `/daily` |
| Rate limit | 앱 단위 토큰 버킷(예: 2 rps), 429 `GW.RATE_LIMIT` |

공식 문서로 바로잡은 내용:
- 택배사 코드: **롯데택배 = `HYUNDAI`, 로젠택배 = `KGB`** (CJ대한통운 `CJGLS`, 한진 `HANJIN`, 우체국 `EPOST`, 경동 `KDEXP` 등. 공식 표 약 200개)
- 주문 상세의 원상품 번호 필드는 `originalProductId` 이고, `productId` 는 채널상품 번호다. 배송지는 `shippingAddress{name, tel1, baseAddress, detailedAddress, zipCode}` 이다.
- 상품 주문 상태: PAYMENT_WAITING, PAYED, DELIVERING, DELIVERED, PURCHASE_DECIDED, EXCHANGED, CANCELED, RETURNED, CANCELED_BY_NOPAYMENT. 클레임: CANCEL, RETURN, EXCHANGE, PURCHASE_DECISION_HOLDBACK, ADMIN_CANCEL

가격과 재고 변경은 원상품 조회 후 수정 방식으로 구현했다. 옵션 단위 처리가 필요하면 option-stock API 로 교체한다.
