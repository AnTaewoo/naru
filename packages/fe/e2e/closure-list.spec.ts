// T5.9 통제 목록 — iPhone 13 크기. 개발 DB 의 실제 사건(recorded closure_events 와 같은 배치):
// 11/7 15:00 서울경찰청 집회 r04 = 파서 요약 "시의회~숭례문오거리 집회 → 광화문·고용노동청 행진",
// 50,000명·태평로, 서로 다른 횡단보도 31곳. 기준 시각은 경찰청 11/6 공지 · 마라톤 3/12 시각표
import { devices, expect, test } from "@playwright/test";
import { consoleErrors, expandSheet, ownErrors } from "./helpers";

const iphone = devices["iPhone 13"];
test.use({
  viewport: iphone.viewport,
  deviceScaleFactor: iphone.deviceScaleFactor,
  isMobile: iphone.isMobile,
  hasTouch: iphone.hasTouch,
  userAgent: iphone.userAgent,
});

const RALLY = "시의회~숭례문오거리 집회 → 광화문·고용노동청 행진";
const EXCERPT =
  "15:00~16:00 시의회~숭례문R → 광화문·고용노동청 <태평로 등> 50,000명 중부, 종로, 남대문";

test("11/7 15:00 홈 — 파서 제목·둘째 줄·사건 전체 31곳·기준 시각, 원문은 '공지 원문 보기'에서만, 지도를 옮겨도 31곳", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto("/?t=2026-11-07T15:00:00+09:00");
  const sheet = page.getByRole("region", { name: "11월 7일 통제" });
  await expect(sheet).toContainText(RALLY);
  await expect(sheet).toContainText("5만 명 · 태평로");
  await expect(sheet).toContainText("15:00–16:00 · 횡단보도 31곳");
  await expect(sheet).toContainText("경찰청 11/6 공지 · 마라톤 3/12 시각표 기준");
  await expect(sheet).toContainText("실시간 돌발(TOPIS)은 아직 받지 않아요");
  await expect(sheet).not.toContainText("확신");
  await expect(sheet).not.toContainText(EXCERPT);
  // 기준 시각이 실제 지금이 아니면 '지금' 배지 대신 돌아가는 버튼 (T5.9)
  await expect(page.getByRole("button", { name: "지금 시각으로" })).toBeVisible();
  // 지도를 끌어 화면 영역이 바뀌어도 사건 전체 수는 그대로 (예전: 31곳 → 20곳)
  const closures = page.waitForResponse((r) => r.url().includes("/api/closures?"));
  const canvas = page.locator("canvas.maplibregl-canvas");
  const box = await canvas.boundingBox();
  const x = (box?.x ?? 0) + (box?.width ?? 0) * 0.5;
  const y = (box?.y ?? 0) + (box?.height ?? 0) * 0.3;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x - 120, y - 60, { steps: 6 });
  await page.mouse.up();
  await closures;
  await expect(sheet).toContainText("15:00–16:00 · 횡단보도 31곳");
  // 보고용 화면: 시트를 '전체'로 끌어 올리고(손잡이) 집회 행이 보이게 — 원문은 누른 뒤에만
  const grip = sheet.getByRole("button", { name: "시트 높이" });
  const g = await grip.boundingBox();
  const gx = (g?.x ?? 0) + (g?.width ?? 0) / 2;
  const gy = (g?.y ?? 0) + (g?.height ?? 0) / 2;
  await page.mouse.move(gx, gy);
  await page.mouse.down();
  await page.mouse.move(gx, gy - 320, { steps: 8 });
  await page.mouse.up();
  await expect(sheet).toHaveAttribute("data-stage", "full");
  const row = sheet.locator("div", { hasText: RALLY }).last();
  await row.getByRole("button", { name: "공지 원문 보기" }).click();
  await expect(sheet).toContainText(EXCERPT);
  await sheet.getByText(RALLY).scrollIntoViewIfNeeded();
  await page.waitForTimeout(300);
  await page.screenshot({ path: "test-results/iphone13-t59-list.png" });
  expect(ownErrors(errors)).toEqual([]);
});

test("통제 불러오기 — 끝난 사건은 '지난 통제' 묶음, 제목은 파서 요약", async ({ page }) => {
  await page.goto("/?t=2026-11-07T15:00:00+09:00");
  await expandSheet(page, "11월 7일 통제");
  await page.getByRole("button", { name: "통제 불러오기" }).first().click();
  const list = page.getByRole("region", { name: "통제 불러오기" });
  const past = list.getByRole("group", { name: "지난 통제" });
  await expect(past).toContainText(RALLY);
  await expect(past).toContainText("마라톤 1구간 세종대로 사거리~숭례문 오거리");
  await expect(list).not.toContainText(EXCERPT);
});
