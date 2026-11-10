// T7.10 ☆ 이 근처 알림 받기 — iPhone 13 크기. Playwright 컨텍스트는 시크릿이라 Push API 구독이 안 된다
// (crbug 401439): 권한을 줘도 subscribe 가 실패해 '구독을 만들지 못했어요' 까지 본다. 실제 구독은 영속 프로필
// (scripts/record_push_subscription.py)·운영(태우 PC Chrome·폰, PC-7B)에서
import { devices, expect, test } from "@playwright/test";
import { consoleErrors, ownErrors } from "./helpers";

test.use({
  viewport: devices["iPhone 13"].viewport,
  deviceScaleFactor: devices["iPhone 13"].deviceScaleFactor,
  isMobile: true,
  hasTouch: true,
  permissions: ["notifications"],
});

test("사건 카드의 ☆ — 누르면 구독을 시도하고(시크릿 창이라 실패) 까닭을 알린다; /licenses 에 알림·개인정보 절", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto("/?t=2026-11-07T13:00:00%2B09:00&event=be5f89a4ebf3");
  const card = page.getByRole("article", { name: /동화면세점/ });
  await expect(card).toBeVisible();
  const star = card.getByRole("button", { name: "☆ 이 근처 알림 받기" });
  await expect(star).toBeVisible();
  const key = page.waitForResponse((r) => r.url().includes("/api/push/vapid-public-key"));
  await star.click();
  expect((await key).status()).toBe(200);
  await expect(card.getByRole("status")).toContainText("구독을 만들지 못했어요", {
    timeout: 15_000,
  });
  await expect(card.getByRole("button", { name: "☆ 이 근처 알림 받기" })).toBeVisible();
  await page.goto("/licenses");
  await expect(page.getByRole("heading", { name: "알림과 개인정보" })).toBeVisible();
  await expect(page.getByText(/150 m 격자로 뭉개 3시간/)).toBeVisible();
  // 구독 실패는 브라우저가 콘솔에 남길 수 있다 — 그 밖의 오류는 없어야 한다
  expect(ownErrors(errors).filter((e) => !/push|Push|AbortError/.test(e))).toEqual([]);
});
