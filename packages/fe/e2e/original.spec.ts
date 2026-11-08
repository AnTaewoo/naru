// T5.11 원래 길 보기 — iPhone 13 크기. recorded route_0745 질의(교보빌딩 → 대한문, 07:45 통제 중 2곳)와
// 태우 실서버 요청 11/7 15:00 세종대로 건너기(공지상 통제 시간 1곳). 원래 길 카드를 누르면 원래 길을 고르고
// 시트가 접힌다 — 지도에는 원래 길 실선과 지나는 통제 횡단보도의 원(빨강·주황)이 그려진다 (화면으로 확인)
import { devices, expect, test, type Page } from "@playwright/test";
import { recorded } from "../src/test/recorded";
import { consoleErrors, expandSheet, ownErrors } from "./helpers";

const iphone = devices["iPhone 13"];
test.use({
  viewport: iphone.viewport,
  deviceScaleFactor: iphone.deviceScaleFactor,
  isMobile: iphone.isMobile,
  hasTouch: iphone.hasTouch,
  userAgent: iphone.userAgent,
});

const q = recorded("route_0745").query ?? {};

function cardButton(page: Page, name: "가장 빠른 길" | "원래 길") {
  return page.getByRole("article", { name }).getByRole("button");
}

test("07:45 — 원래 길(지금 못 감) 카드를 누르면 원래 길을 고르고 시트가 접힌다, 다시 가장 빠른 길로", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto(`/?t=2026-03-15T07:45:00+09:00&from=${q["from"] ?? ""}&to=${q["to"] ?? ""}`);
  await expect(page.getByRole("article", { name: "가장 빠른 길" })).toContainText("12분");
  const sheet = page.getByRole("region", { name: "길찾기 결과" });
  await expandSheet(page, "길찾기 결과");
  await expect(cardButton(page, "원래 길")).toContainText("지금 못 감");
  await cardButton(page, "원래 길").click();
  await expect(cardButton(page, "원래 길")).toHaveAttribute("aria-pressed", "true");
  await expect(cardButton(page, "가장 빠른 길")).toHaveAttribute("aria-pressed", "false");
  await expect(sheet).toHaveAttribute("data-stage", "collapsed");
  await page.waitForTimeout(2000); // 원래 길에 맞추는 애니메이션·타일
  await page.screenshot({ path: "test-results/iphone13-t511-original.png" });
  await expandSheet(page, "길찾기 결과");
  await cardButton(page, "가장 빠른 길").click();
  await expect(cardButton(page, "가장 빠른 길")).toHaveAttribute("aria-pressed", "true");
  expect(ownErrors(errors)).toEqual([]);
});

test("11/7 15:00 — 공지상 통제 시간인 원래 길 카드도 눌린다", async ({ page }) => {
  const errors = consoleErrors(page);
  await page.goto("/?t=2026-11-07T15:00:00+09:00&from=37.56368,126.97230&to=37.56368,126.98193");
  await expect(page.getByRole("article", { name: "가장 빠른 길" })).toContainText("16분");
  await expandSheet(page, "길찾기 결과");
  await expect(cardButton(page, "원래 길")).toContainText("공지상 통제 시간");
  await cardButton(page, "원래 길").click();
  await expect(cardButton(page, "원래 길")).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: "test-results/iphone13-t511-original-1107.png" });
  expect(ownErrors(errors)).toEqual([]);
});
