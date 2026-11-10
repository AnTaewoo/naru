// T5.5 라우터 정확성 회귀 (ADR-011) — iPhone 13 크기로. 좌표·시각은 태우가 2026-11-08 실서버에 보낸 요청.
// ② 11/7 15:00 세종대로 건너기: 예정 집회(공지 창 안)를 시청 지하보도로 피하고 "공지상 통제 시간" 표기
//    (recorded naru_api/route_1107_1500.json — 935 s·1,122.5 m, 예정 1곳 16:00까지, 원래 길 871 s)
// ① 경기 성남: 그래프 밖 → 범위 밖 안내. T6.9 부터 보행망이 서울 전체라 잠실(옛 회귀)은 안이다 — 태우 2026-11-09
//    지점 37.3947,127.1112 → 37.3960,127.1150 (BE test_route_regressions SEONGNAM 과 같다)
// ④ 3/15 07:45 공유 링크(?t=…%2B09:00&from=&to=) — 날짜·시각·출발·도착이 그대로 열리고 마라톤 통제 중이라 지하보도(T7.6)
// ⑤ 이 구역 피해서 길찾기(T7.6, INTERFACE §2 v0.14 avoid) — 3/15 13:30 마라톤 1구간(adaea2f4cc02) 카드 → 길찾기,
//    공유 링크 ?avoid= 는 기록 route_avoid_1330 과 같은 길(680 s·816.1 m, 피한 23206 released)
import { devices, expect, test } from "@playwright/test";
import { recorded } from "../src/test/recorded";
import { consoleErrors, expandSheet, ownErrors } from "./helpers";

const q745 = recorded("route_0745").query ?? {};
const od745 = `from=${q745["from"] ?? ""}&to=${q745["to"] ?? ""}`;
const SEG1 = "마라톤 1구간 세종대로 사거리~숭례문 오거리";

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
  // 통제 근거: 원본 출처 줄(공지 게시 시각·"서울경찰청 집회 공지"·[공지] 칸)은 쓰지 않는다 (태우 2026-11-08)
  await expandSheet(page, "길찾기 결과");
  await page.getByRole("button", { name: "통제 근거" }).click();
  const ev = page.getByRole("region", { name: "통제 근거" });
  await expect(ev).toContainText("~16:00");
  await expect(ev).not.toContainText("서울경찰청");
  await expect(ev).not.toContainText("11/6 18:00");
  await ev.getByText("확신도").scrollIntoViewIfNeeded();
  await page.screenshot({ path: "test-results/iphone13-t58-evidence.png" });
  expect(ownErrors(errors)).toEqual([]);
});

test("① 경기 성남(그래프 밖) — 범위 밖 안내", async ({ page }) => {
  // 422 응답은 브라우저 콘솔에 리소스 오류로 남는다 — 여기선 콘솔을 보지 않는다
  await page.goto("/?t=2026-03-15T10:00:00+09:00&from=37.3947,127.1112&to=37.3960,127.1150");
  await expect(page.getByText("이 위치는 아직 길찾기 범위(서울) 밖이에요")).toBeVisible();
});

test("④ 3/15 07:45 공유 링크 — 날짜·시각·출발·도착이 그대로, 마라톤 통제 중이라 지하보도 (T7.6)", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto(`/?t=2026-03-15T07:45:00%2B09:00&${od745}`);
  const fast = page.getByRole("article", { name: "가장 빠른 길" });
  await expect(fast).toContainText("12분");
  await expect(fast).toContainText("지하보도 1");
  await expect(page.getByRole("article", { name: "원래 길" })).toContainText("지금 못 감");
  await expandSheet(page, "길찾기 결과");
  await expect(page.getByLabel("날짜")).toHaveValue("2026-03-15");
  await expect(page.getByRole("region", { name: "길찾기 결과" })).toContainText("07:45");
  expect(ownErrors(errors)).toEqual([]);
});

test("⑤ 이 구역 피해서 길찾기 — 1구간 카드 버튼 → 길찾기 '피하는 구역', ?avoid= 공유 링크는 23206 을 비켜 816m (T7.6)", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto("/?t=2026-03-15T13:30:00%2B09:00&event=adaea2f4cc02");
  const card = page.getByRole("article", { name: SEG1 });
  await card.getByRole("button", { name: "이 구역 피해서 길찾기" }).click();
  const sheet = page.getByRole("region", { name: "길찾기 결과" });
  await expect(sheet).toContainText(`피하는 구역 · ${SEG1}`);
  await page.goto(`/?t=2026-03-15T13:30:00%2B09:00&${od745}&avoid=adaea2f4cc02`);
  await expect(page.getByRole("article", { name: "가장 빠른 길" })).toContainText("816m");
  const orig = page.getByRole("article", { name: "원래 길" });
  await expect(orig).toContainText("피한 구역");
  await expect(orig).toContainText("횡단보도 피한 구역 1곳");
  await expect(sheet).toContainText("고른 구역의 횡단보도 1곳을 피해 돌아가는 길을 골랐어요.");
  await page.waitForTimeout(2000);
  await page.screenshot({ path: "test-results/route-avoid-1330.png" });
  expect(ownErrors(errors)).toEqual([]);
});
