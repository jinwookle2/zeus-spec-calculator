# 구현 계획 및 현황

## Phase 1: 공식 API 및 오픈소스 분석 (완료)

조사일: 2026-11-05. 각 저장소를 shallow clone 해서 최신 커밋 날짜와 라이선스 파일을 직접 확인했다.

| 프로젝트 | 내용 | 라이선스 | 최근 커밋 | 참고한 점 / 주의 |
|---|---|---|---|---|
| commerce-api-naver/commerce-api | 네이버 커머스API 기술지원 공간. `docs/2.0.0-RC.js` 에 OpenAPI 3.0.3 스펙(상품 영역) | LICENSE 파일 없음. 스펙 본문에 "ⓒ NAVER Corp. All Rights Reserved" | 2026-09-23 | 토큰/서명/상품 v2/판매상태/Rate limit 을 **공식 근거**로 사용. 스펙 문서 자체는 복제하지 않음 |
| johunsang/smartku | 스마트스토어·쿠팡 통합관리 데스크톱 앱 (Tauri/Rust, SQLite) | **PolyForm Noncommercial 1.0.0** (상업적 이용 금지) | 2026-08-02 | **코드 미사용.** 문서의 API 경로(주문/이미지/카테고리)만 사실 확인용 2차 출처로 참고. 패턴 참고: 마켓별 Adapter 분리, 등록 전 필수값 검증, 원격 스냅샷에서 개인정보 제거 |
| Alifaizllc/AI-Ecommerce-Operations-Automation | n8n + LLM 의도 분류 → WooCommerce/Airtable | 라이선스 파일 없음 (NOTICE 만) | 2026-09-13 | **코드 미사용.** WooCommerce API 로, 네이버와 무관. 패턴만 참고: LLM 은 분류/표현만, 실행은 결정적 분기 |
| arthgohen/inventory-sync-n8n | Shopify↔WooCommerce 재고 동기화 (n8n+MySQL+Redis) | 라이선스 파일 없음 | 2025-11-05 (1커밋, 유지보수 미약) | **코드 미사용.** 패턴 참고: 단방향 토글 환경변수, 대사(reconcile) 크론, DLQ 테이블, 알림 |
| n8n 주문·배송 템플릿 | n8n.io/workflows 목록 페이지에서 개별 템플릿을 특정하지 못함 (검색 파라미터 미동작) | — | — | 일반 패턴(스케줄 → HTTP → 분기 → 알림)으로 자체 워크플로 작성 |

플랫폼 혼동 방지: Shopify, WooCommerce, Coupang API 형식은 사용하지 않았다. 네이버 연동 코드는 `backend/app/naver/` 에만 있다.

**공식 문서 재확인 (2026-11-05)**: apicenter 공식 문서 v2.91.0 에서 사용하는 모든 엔드포인트를 확인했다(목록은 architecture.md §7). 이 확인으로 택배사 코드 2건(롯데 `HYUNDAI`, 로젠 `KGB`)과 주문의 원상품 번호 필드명(`originalProductId`)을 수정했고, 주문 조회를 24시간 단위 구간으로 나누도록 바꿨다.

## 구현 가능 vs 계약/승인 필요

| 구분 | 기능 | 상태 |
|---|---|---|
| ✅ 지금 구현·검증 완료 | Adapter 구조, Mock/CSV·Excel Adapter, 중복·품절·단종 감지, 상품코드 매핑 | 완료 |
| ✅ | AI 가공(Claude + 규칙 기반 폴백), 사실 날조 방지 guardrail, 고시정보 검증, 옵션 표준화 | 완료 |
| ✅ | 가격/마진 엔진(수수료·광고비·변동비 설정), 최소 이익 미달 등록 차단 | 완료 |
| ✅ | 네이버 OAuth 서명·토큰 갱신, Rate limit/재시도, 상품 등록·수정·상태변경, 주문 조회·발송 (Mock + Live Dry-run) | 완료 |
| ✅ | 주문 상태 머신, 감사 로그, 중복 수집/발주 방지, 재시도, DLQ, 재고 불일치 시 자동발주 중단, 일일 발주 한도 | 완료 |
| ✅ | 관리자 14개 메뉴, 역할 권한, PII 암호화·마스킹, Docker Compose, n8n 예시 | 완료 |
| 🔑 계정 필요 | 네이버 실연동 검증: 커머스API센터 애플리케이션(Client ID/Secret), 판매자 계정 | 사용자 제공 필요 |
| 🔑 | Claude 실호출: `ANTHROPIC_API_KEY` (없으면 규칙 기반으로 동작) | 사용자 제공 필요 |
| 📄 계약 필요 | 실제 공급사 Adapter (상품 API/피드 명세, 인증, 발주 API, 송장 API, 취소 API) | 공급사별 명세 필요 |
| 📄 | 공급사 이미지 사용 허락, 브랜드 판매권한 목록, 개인정보 위탁/제공 계약 | 계약서 필요 |
| 📄 | 공급사 결제 방식(예치금/카드/후불), 반품·교환 처리 절차 | 계약서 필요 |

## Phase 2~8 진행 현황

- **Phase 2 아키텍처·DB**: `architecture.md`, `backend/app/models.py` ✅
- **Phase 3 공급사 Mock Adapter**: `backend/app/adapters/` ✅ (Mock 은 정상, 브랜드, 금지어, 품절, 시장가, 중복, 고시누락, 단종 시나리오 포함)
- **Phase 4 가공·마진**: `services/ai_processor.py`, `compliance.py`, `pricing.py` ✅
- **Phase 5 네이버 등록**: `naver/`, `services/listing.py` ✅ (Live 는 Dry-run 까지 검증)
- **Phase 6 주문·발주·배송**: `services/fulfillment.py`, `order_state.py` ✅
- **Phase 7 관리자**: `frontend/` ✅
- **Phase 8 테스트·배포**: pytest 47개(SQLite, PostgreSQL 모두 통과), Playwright E2E 1개, docker-compose ✅ (이 개발 환경에는 Docker 데몬이 없어 이미지 빌드는 미검증, compose 문법만 검증)

## 운영 전환 단계 (권장 순서)

1. **Mock 운영 리허설**: `NAVER_MODE=mock` 으로 관리자 화면 전체 흐름 확인
2. **네이버 읽기 연동**: `NAVER_MODE=live`, 모든 `ALLOW_*=false`. '네이버 연결 테스트'로 토큰을 발급해 `NAVER_SIGN_B64`(standard/urlsafe) 확정. 카테고리/원산지코드/고시정보 상품군 확인 후 `origin_area_codes` 입력
3. **Dry-run 등록 검증**: 승인한 상품을 등록 실행하고 '오류 및 알림 → 외부 API 호출 기록'에서 요청 본문 확인
4. **소량 실등록**: `ALLOW_PUBLIC_LISTING=true`, `daily_listing_limit` 를 1~3 으로. 등록 결과를 스마트스토어 센터에서 확인
5. **실제 공급사 Adapter 개발**: 계약된 명세로 `SupplierAdapter` 구현. 계약 테스트 작성. `verified=false` 로 시작
6. **주문 처리 수동 승인 운영**: `ALLOW_NAVER_ORDER_ACTIONS=true`, 공급사 `auto_purchase_allowed=false` 상태에서 관리자 승인 발주
7. **자동 발주 단계 확대**: 문제가 없으면 해당 공급사 `verified/auto_purchase_allowed=true`, `ALLOW_REAL_PURCHASE=true`, 일일 발주 금액 한도는 작게 시작
8. **개인정보 전송**: 위탁 계약 확인 후 공급사 `pii_transfer_agreed=true` + `ALLOW_PII_TRANSFER=true`

## 추가 완료 (2026-11-08)
- Alembic 마이그레이션 + 기동 시 자동 적용 + revision 누락 검사 테스트
- 네이버 카테고리 동기화와 동기화 카테고리 기반 추천, 관리자 화면 카테고리 검색·변경
- 등록 전 제한 태그 제거 (`/v2/tags/restricted-tags`)
- 교환 수거 완료 / 교환 재배송 처리 (API + 화면)
- 네이버 건별 정산 대사와 수수료 불일치 알림, 매출 분석에 실제 수수료 반영
- 로그인 잠금(5회/15분), 비밀번호 변경 화면

## 남은 작업 (미구현 / 개선)
- 실제 계정으로 주문 응답 샘플을 받아 파서 검증 (필드명은 공식 문서와 대조 완료)
- 상품군별 고시정보 스키마 자동 매핑 (현재 ETC 상품군 기본값)
- 옵션 단위 재고/가격 동기화 (현재 상품 단위 + 옵션 재고 참고)
- 반품 시 공급사 반품 접수, 교환 재배송분의 공급사 재발주 (현재 수동)
- 2단계 인증(2FA), 관리자 화면의 사용자 관리 (API 는 있음)
- 정산 응답 실데이터 확인: 수수료 금액 부호(차감 표기)는 절댓값으로 비교하도록 구현함
- Claude 호출: 실제 API 키로 품질 평가(eval) 후 프롬프트 조정. 서버측 refusal fallback 은 규칙 기반 폴백으로 대체
