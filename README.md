# Naver SmartStore AI Dropshipping Automation

네이버 스마트스토어 위탁판매 운영 시스템입니다. 소싱, AI 가공, 등록, 재고, 주문 수집, 공급사 발주, 배송, 매출 분석을 자동화합니다.

- 설계: [architecture.md](architecture.md)
- 조사 결과, 구현 범위, 운영 전환 단계: [implementation_plan.md](implementation_plan.md)
- 환경변수: [.env.example](.env.example)

> **기본값은 안전 모드입니다.** `NAVER_MODE=mock` 이고 모든 `ALLOW_*` 스위치가 `false` 입니다.
> 실제 상품 공개 등록, 공급사 결제, 고객 개인정보 전송, 네이버 발송처리는 해당 스위치를 명시적으로 켜기 전까지 실행되지 않습니다(Dry-run 으로 기록만 됨).

## 구조
```
backend/   FastAPI · SQLAlchemy · Celery  (app/adapters, app/naver, app/services, tests)
frontend/  Next.js 15 · Tailwind 관리자 (14개 메뉴, Playwright E2E)
n8n/       선택: 스케줄/알림 워크플로 예시
docker-compose.yml  db · redis · api · worker · beat · web (+ n8n 프로필)
```

## 빠른 시작 (Docker)
```bash
cp .env.example .env     # JWT_SECRET, SERVICE_TOKEN, BOOTSTRAP_ADMIN_PASSWORD, PII_ENCRYPTION_KEY 채우기
docker compose up -d --build
# 관리자: http://localhost:3000  (BOOTSTRAP_ADMIN_EMAIL / PASSWORD)
# API 문서: http://localhost:8000/docs
docker compose --profile n8n up -d n8n   # 선택
```

## 로컬 개발 (Docker 없이)
```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
uvicorn app.main:app --reload --port 8000          # 기본 SQLite(./dropship.db), mock 모드
celery -A app.celery_app worker -l info            # Redis 필요 (REDIS_URL)
celery -A app.celery_app beat -l info

cd ../frontend && npm install
BACKEND_URL=http://localhost:8000 npm run dev      # http://localhost:3000
```
로컬 기본 관리자는 `admin@example.com` / `admin1234!` 입니다. 운영에서는 반드시 `.env` 로 바꾸세요.

## DB 마이그레이션
API 가 시작될 때 자동으로 적용됩니다(`DB_AUTO_MIGRATE=true`). 직접 실행하려면:
```bash
cd backend && alembic upgrade head
alembic revision --autogenerate -m "설명"   # 모델 변경 후
```

## 테스트
```bash
cd backend && pytest                                         # SQLite
TEST_DATABASE_URL=postgresql+psycopg2://user@host/db pytest  # PostgreSQL
cd frontend && npx playwright test                           # API(:8000) + web(:3000) 실행 상태에서
```

## Mock 으로 전체 흐름 보기
1. 대시보드 → **전체 파이프라인 지금 실행**: 수집 → 가공 → 검증 → 가격 → 자동 승인(검증된 공급사 A) → 등록
2. **상품 등록 대기**: 차단 사유(브랜드 권한, 금지어, 시장가 초과, 고시정보 누락)와 공급사 B 승인 대기 확인 → 승인
3. **등록 상품 관리 → Mock 주문** → **주문 관리**: 주문 수집 → 재고 확인·발주 처리
4. **배송 관리 → 송장 수집 실행**: 택배사 코드 매핑 → 네이버 발송처리 → `TRACKING_REGISTERED`
5. **오류 및 알림 / 매출 및 수익 분석** 확인
