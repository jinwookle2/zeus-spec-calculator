import { createHmac } from "crypto";
import { expect, test } from "@playwright/test";

function totp(secret: string): string {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const c of secret.replace(/=+$/, "")) bits += alphabet.indexOf(c).toString(2).padStart(5, "0");
  const key = Buffer.from(bits.match(/.{8}/g)!.map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 1000 / 30)));
  const h = createHmac("sha1", key).update(counter).digest();
  const o = h[h.length - 1] & 0xf;
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1_000_000).padStart(6, "0");
}

async function login(page: any, otp?: string) {
  await page.goto("/login");
  await page.fill("input[name=email]", "admin@example.com");
  await page.fill("input[name=password]", process.env.E2E_ADMIN_PASSWORD || "admin1234!");
  await page.click("button[type=submit]");
  if (otp !== undefined) {
    await expect(page.locator("input[name=otp]")).toBeVisible();
    await page.fill("input[name=otp]", otp);
    await page.click("button[type=submit]");
  }
  await expect(page.getByRole("heading", { name: "대시보드" })).toBeVisible();
}

test("관리자: 사용자 추가 → 2단계 인증 설정 → OTP 로그인 → 해제", async ({ page }) => {
  await login(page);
  await page.getByRole("link", { name: "사용자 관리" }).click();
  const email = `e2e${Date.now()}@example.com`;
  await page.getByPlaceholder("이메일").fill(email);
  await page.getByPlaceholder("초기 비밀번호 (10자 이상)").fill("e2epassword123");
  await page.getByTestId("add-user").click();
  await expect(page.getByTestId("users-table").getByText(email)).toBeVisible();

  await page.goto("/account");
  await page.getByTestId("otp-setup").click();
  const secret = (await page.getByTestId("otp-secret").textContent())!.trim();
  await page.getByTestId("otp-code").fill(totp(secret));
  await page.getByTestId("otp-enable").click();
  await expect(page.getByText("2단계 인증을 켰습니다")).toBeVisible();

  await page.evaluate(() => localStorage.clear());
  await login(page, totp(secret));

  await page.goto("/account");
  await page.getByPlaceholder("비밀번호", { exact: true }).fill("admin1234!");
  await page.getByPlaceholder("OTP 코드").fill(totp(secret));
  await page.getByRole("button", { name: "2단계 인증 끄기" }).click();
  await expect(page.getByText("2단계 인증을 껐습니다")).toBeVisible();
});
