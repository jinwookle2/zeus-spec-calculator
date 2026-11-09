import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  workers: 1, // 테스트가 같은 DB 상태를 공유하므로 순차 실행
  use: { baseURL: process.env.E2E_BASE_URL || "http://localhost:3000", viewport: { width: 1400, height: 900 } },
  reporter: [["list"]],
});
