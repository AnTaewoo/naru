// T7.16 행진 예상 위치 — iPhone 13. 실제 앱(임시 스택 naru_test, BE 0007): 11/7 r01 동화면세점 고리(be5f89a4ebf3,
// 12:00~16:00, 기록 march_be5f89a4ebf3)를 13:00 에 열면 카드에 "이 시각 막혀 있을 확률 100%"(세종대로사거리) +
// 재생, 지도에 heatmap 점(data-march). r04(2e930ec6deeb)는 갈라진 행진이라 404 → 줄 없음
import { devices, expect, test } from "@playwright/test";
import { consoleErrors, ownErrors } from "./helpers";

const iphone = devices["iPhone 13"];
test.use({
  viewport: iphone.viewport,
  deviceScaleFactor: iphone.deviceScaleFactor,
  isMobile: iphone.isMobile,
  hasTouch: iphone.hasTouch,
  userAgent: iphone.userAgent,
});

const R01 = "be5f89a4ebf3";

test("13:00 동화면세점 고리 — 확률 100%·공지 일정 기준 예상 위치, 지도에 예상 위치 점, 재생 → 정지 → 끝나면 다시 재생", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  const march = page.waitForResponse((r) => r.url().includes(`/api/closures/events/${R01}/march`));
  await page.goto(`/?t=2026-11-07T13:00:00%2B09:00&event=${R01}`);
  expect((await march).status()).toBe(200);
  const card = page.getByRole("article").filter({ hasText: "막혀 있을 확률" });
  await expect(card).toContainText("이 시각 막혀 있을 확률 100%");
  await expect(card).toContainText("공지 일정 기준 예상 위치");
  const map = page.locator("[data-march]");
  await expect
    .poll(async () => Number(await map.getAttribute("data-march")), { timeout: 15_000 })
    .toBeGreaterThan(0);
  await card.getByRole("button", { name: "예상 위치 재생" }).click();
  await expect(card.getByRole("button", { name: "정지" })).toBeVisible();
  await expect(card).toContainText("통제 시간 전체를 12초에");
  // 통제 시간 전체를 12초에 — 끝나면 저절로 멈춘다
  await expect(card.getByRole("button", { name: "예상 위치 재생" })).toBeVisible({
    timeout: 20_000,
  });
  expect(ownErrors(errors)).toEqual([]);
});

test("갈라진 행진(r04)은 모델이 없다 — 404 not_modeled, 카드에 확률 줄 없음", async ({ page }) => {
  const errors = consoleErrors(page);
  const march = page.waitForResponse((r) =>
    r.url().includes("/api/closures/events/2e930ec6deeb/march"),
  );
  await page.goto("/?t=2026-11-07T15:30:00%2B09:00&event=2e930ec6deeb");
  expect((await march).status()).toBe(404);
  const card = page.getByRole("article", { name: /행진/ });
  await expect(card).toBeVisible();
  await expect(card).not.toContainText("막혀 있을 확률");
  expect(await page.locator("[data-march]").getAttribute("data-march")).toBe("0");
  expect(ownErrors(errors)).toEqual([]); // 행진 404 not_modeled 은 helpers.ownErrors 가 뺀다
});
