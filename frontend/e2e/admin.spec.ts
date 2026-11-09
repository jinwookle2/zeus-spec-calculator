import { expect, test } from "@playwright/test";

test("관리자: 로그인 → 파이프라인 → Mock 주문 → 발주 → 송장 등록까지", async ({ page }) => {
  await page.goto("/login");
  await page.fill("input[name=email]", "admin@example.com");
  await page.fill("input[name=password]", process.env.E2E_ADMIN_PASSWORD || "admin1234!");
  await page.click("button[type=submit]");
  await expect(page.getByRole("heading", { name: "대시보드" })).toBeVisible();
  await expect(page.getByTestId("mode-badge")).toHaveText(/MOCK/);

  await page.getByTestId("run-pipeline").click();
  await expect(page.getByText("전체 파이프라인 실행 완료")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("link", { name: "등록 상품 관리" }).click();
  const firstMock = page.locator("[data-testid^=mock-order-]").first();
  await expect(firstMock).toBeVisible();
  await firstMock.click();
  await expect(page.getByText(/Mock 주문 생성/)).toBeVisible();

  await page.getByRole("link", { name: "주문 관리" }).click();
  await page.getByTestId("collect-orders").click();
  await expect(page.getByText(/주문 수집:.*"new":1/)).toBeVisible();
  await page.getByTestId("process-orders").click();
  await expect(page.getByTestId("orders-table").getByText("SUPPLIER_CONFIRMED")).toBeVisible();

  await page.getByRole("link", { name: "배송 관리" }).click();
  await page.getByTestId("poll-shipments").click();
  await expect(page.getByTestId("shipments-table").getByText("TRACKING_REGISTERED")).toBeVisible();
  await expect(page.getByTestId("shipments-table").getByText(/CJ → CJGLS/)).toBeVisible();

  await page.getByRole("link", { name: "매출 및 수익 분석" }).click();
  await page.getByTestId("reconcile").click();
  await expect(page.getByText(/정산 대사:.*"matched":[1-9]/)).toBeVisible();
  await expect(page.getByTestId("settlements-table").getByText("NORMAL_SETTLE_ORIGINAL")).toBeVisible();

  await page.getByRole("link", { name: "API 연결 설정" }).click();
  await page.getByTestId("sync-categories").click();
  await expect(page.getByText(/"created":\d+/)).toBeVisible();

  await page.getByRole("link", { name: "상품 등록 대기" }).click();
  await expect(page.getByTestId("queue-table").getByText(/BRAND_NOT_AUTHORIZED/).first()).toBeVisible();

  await page.getByRole("link", { name: "가격 및 마진 관리" }).click();
  await page.getByTestId("simulate").click();
  await expect(page.getByTestId("sim-suggested")).toContainText("✅");

  await page.getByRole("link", { name: "자동화 설정" }).click();
  await page.getByTestId("f-daily_listing_limit").fill("30");
  await page.getByTestId("f-target_margin_rate").fill("0.3");
  await page.getByTestId("save-settings").click();
  await expect(page.getByText(/저장됨: target_margin_rate/)).toBeVisible();
});
