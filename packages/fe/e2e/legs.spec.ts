// T5.10 경로 상세 — iPhone 13 크기. recorded route_0745 질의(교보빌딩 → 대한문, 07:45): 레그 7개, 횡단보도
// 레그 이름은 OA-23081 교차로명 "청계광장"(06-0000002137). 경로 종류가 하나라 패널에 탭 줄이 없다
import { devices, expect, test } from "@playwright/test";
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

test("경로 상세 — 횡단보도 레그에 교차로명, 탭 줄 없음", async ({ page }) => {
  const errors = consoleErrors(page);
  await page.goto(`/?t=2026-03-15T07:45:00+09:00&from=${q["from"] ?? ""}&to=${q["to"] ?? ""}`);
  await expect(page.getByRole("article", { name: "가장 빠른 길" })).toContainText("12분");
  await expect(page.getByRole("tablist")).toHaveCount(0);
  await expandSheet(page, "길찾기 결과");
  await page.getByRole("button", { name: "경로 상세" }).click();
  const rows = page.getByRole("list", { name: "경로 상세" }).getByRole("listitem");
  await expect(rows).toHaveCount(7);
  await expect(rows.nth(2)).toContainText("광화문(세종문화회관) 지하보도");
  await expect(rows.nth(5)).toContainText("청계광장");
  await expect(rows.nth(5)).toContainText("횡단보도");
  await rows.nth(5).scrollIntoViewIfNeeded();
  await page.waitForTimeout(800);
  await page.screenshot({ path: "test-results/iphone13-t510-legs.png" });
  expect(ownErrors(errors)).toEqual([]);
});
