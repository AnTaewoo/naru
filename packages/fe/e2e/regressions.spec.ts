// T5.5 라우터 정확성 회귀 (ADR-011) — iPhone 13 크기로. 좌표·시각은 태우가 2026-11-08 실서버에 보낸 요청.
// ② 11/7 15:00 세종대로 건너기: 예정 집회(공지 창 안)를 시청 지하보도로 피하고 "공지상 통제 시간" 표기
//    (recorded naru_api/route_1107_1500.json — 935 s·1,122.5 m, 예정 1곳 16:00까지, 원래 길 871 s)
// ① 잠실: 그래프 밖 → 범위 밖 안내 (recorded naru_api/error_out_of_coverage.json)
import { devices, expect, test } from "@playwright/test";
import { consoleErrors, expandSheet, ownErrors } from "./helpers";

// Playwright 의 iPhone 13 (보이는 영역 390×664, 3배율, 터치) — 브라우저는 설정의 Chrome 그대로
const iphone = devices["iPhone 13"];
test.use({
  viewport: iphone.viewport,
  deviceScaleFactor: iphone.deviceScaleFactor,
  isMobile: iphone.isMobile,
  hasTouch: iphone.hasTouch,
  userAgent: iphone.userAgent,
});

test("② 11/7 15:00 세종대로 건너기 — 예정 집회를 시청 지하보도로 피하고 '공지상 통제 시간'", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto("/?t=2026-11-07T15:00:00+09:00&from=37.56368,126.97230&to=37.56368,126.98193");
  const fast = page.getByRole("article", { name: "가장 빠른 길" });
  await expect(fast).toContainText("16분");
  await expect(fast).toContainText("지하보도 1");
  await expect(page.getByRole("article", { name: "원래 길" })).toContainText("공지상 통제 시간");
  await expect(
    page.getByText(/공지상 통제 시간\(현장 확인 전\)이라 시청 지하보도로 건너는 길을 골랐어요/),
  ).toBeVisible();
  await page.waitForTimeout(2500); // 화면 맞춤·타일 (스크린샷용)
  await page.screenshot({ path: "test-results/iphone13-t55-sejong-1500.png" });
  // 통제 근거: 공지 줄 뒤에 [공지] 칸이 또 붙지 않는다 (태우 2026-11-08)
  await expandSheet(page, "길찾기 결과");
  await page.getByRole("button", { name: "통제 근거" }).click();
  const ev = page.getByRole("region", { name: "통제 근거" });
  await expect(ev).toContainText("서울경찰청 집회 공지");
  await expect(ev).not.toContainText("공지공지");
  await ev.getByText("해제 예정").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "test-results/iphone13-t58-evidence.png" });
  expect(ownErrors(errors)).toEqual([]);
});

test("① 잠실(그래프 밖) — 범위 밖 안내", async ({ page }) => {
  // 422 응답은 브라우저 콘솔에 리소스 오류로 남는다 — 여기선 콘솔을 보지 않는다
  await page.goto("/?t=2026-03-15T10:00:00+09:00&from=37.5133,127.0980&to=37.5145,127.1035");
  await expect(page.getByText("이 위치는 아직 길찾기 범위(종로·중구) 밖이에요")).toBeVisible();
});
