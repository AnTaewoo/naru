// T7.16 행진 예상 위치 — iPhone 13. 실제 앱(임시 스택 naru_test, BE 0007): 11/7 r01 동화면세점 고리(be5f89a4ebf3,
// 12:00~16:00, 기록 march_be5f89a4ebf3)를 13:00 에 열면 카드에 "이 시각 막혀 있을 확률 100%"(세종대로사거리),
// 지도에 heatmap 점(data-march). 시각은 카드 위 슬라이더로(재생 버튼은 11/11 뺌). r04(2e930ec6deeb)는 갈라진 행진이라 404 → 줄 없음
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

test("13:00 동화면세점 고리 — 확률 100%·공지 일정 기준 예상 위치, 지도에 예상 위치 점, 카드 위 슬라이더로 10분 뒤 → 13:10 기준, 재생 버튼 없음", async ({
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
  await expect(card.getByRole("button", { name: /재생/ })).toHaveCount(0);
  // 카드를 연 채 슬라이더(기준 시각)가 보이고, 10분 뒤로 옮기면 기준 줄이 13:10, 예상 위치 점은 그대로 있다
  await expect(page.getByRole("slider", { name: "기준 시각" })).toBeVisible();
  await page.getByRole("button", { name: "10분 뒤" }).click();
  await expect(page.getByRole("region", { name: "서울 통제" })).toContainText(
    "11월 7일 13:10 기준",
  );
  await expect(card).toContainText("막혀 있을 확률");
  await expect
    .poll(async () => Number(await map.getAttribute("data-march")), { timeout: 15_000 })
    .toBeGreaterThan(0);
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
