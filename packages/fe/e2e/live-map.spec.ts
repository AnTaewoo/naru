// T7.4 지금 지도 (ADR-014 A) — iPhone 13 크기. BE 는 사건 v2 기록(scripts/record_live_events.py)과 같은 데이터를
// 워커 발행 경로로 실은 naru_test(경찰청 PDF 3개·코스·공지·TOPIS 공지 6300·TOPIS 통제지도·돌발 11/7·11/9).
// 기대값은 그 기록(data/recorded/naru_api/closure_events_live_1107_1530.json)을 열어 확인한 값
import { devices, expect, test } from "@playwright/test";
import { eventById, recordedLive } from "../src/test/recorded";
import { consoleErrors, ownErrors } from "./helpers";

const iphone = devices["iPhone 13"];
test.use({
  viewport: iphone.viewport,
  deviceScaleFactor: iphone.deviceScaleFactor,
  isMobile: iphone.isMobile,
  hasTouch: iphone.hasTouch,
  userAgent: iphone.userAgent,
});

const HOME = "/?t=2026-11-07T15:30:00%2B09:00";
const SHEET = "11월 7일 15:30 서울 통제"; // 기준 시각이 지금이 아니면 그 날짜·시각 (T7.5)
const live = recordedLive("closure_events_live_1107_1530");
// 경찰청 r04 시의회~숭례문R → 광화문·고용노동청 — 15:00–16:00, 횡단보도 22곳, 공지뿐이라 15:30 에도 예정
const RALLY = "시의회~숭례문오거리 집회 → 광화문·고용노동청 행진";
const EXCERPT = eventById(live.body.events, "2e930ec6deeb").notice?.excerpt ?? "";
const [lng, lat] = eventById(live.body.events, "2e930ec6deeb").centroid ?? [];
const camera = (zoom: number) => `#map=${zoom}/${String(lat)}/${String(lng)}`;

test("앱을 열면 그 시각 서울 사건 — 클러스터, 칩은 사건 수, 시트는 사건 목록(통제 불러오기 없음)", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  const crosswalks: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/closures?")) crosswalks.push(r.url());
  });
  await page.goto(HOME);
  await expect(page.getByRole("region", { name: "지도", exact: true })).toHaveAttribute(
    "data-band",
    "cluster",
  );
  // 통제 중 8 · 예정 5 중 r05 내자R~사직공원 0.65 는 칩·목록에서 뺀다
  const chips = page.getByRole("group", { name: "지도 레이어" }).getByRole("button");
  await expect(chips).toHaveText(["통제 중 8", "예정 4", "예정 구역 0"]);
  const sheet = page.getByRole("region", { name: SHEET });
  await expect(sheet).toContainText("15:30 기준 · 서울 통제 중 8건, 예정 4건");
  await expect(sheet).toContainText(RALLY);
  await expect(sheet).toContainText("5만 명 · 태평로");
  await expect(sheet).toContainText("15:00–16:00 · 횡단보도 22곳");
  await expect(sheet).not.toContainText("내자");
  await expect(sheet).not.toContainText(EXCERPT); // 원문은 카드의 '통제 근거 보기'에서만 (T5.9·T7.5)
  // 지금 서울 통제 묶음 (T7.5) — 통제 중 8 → 1시간 안 시작 4
  await expect(sheet.getByRole("region", { name: "통제 중" }).getByRole("button")).toHaveCount(8);
  await expect(
    sheet.getByRole("region", { name: "1시간 안 시작" }).getByRole("button"),
  ).toHaveCount(4);
  await expect(page.getByRole("button", { name: "통제 불러오기" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "지금 시각으로" })).toBeVisible();
  await page.waitForTimeout(1500);
  expect(crosswalks).toEqual([]); // 서울 전체 화면에선 횡단보도를 받지 않는다
  await page.screenshot({ path: "test-results/live-map-seoul.png" });
  expect(ownErrors(errors)).toEqual([]);
});

test("줌 12~15 는 사건 구역 — 횡단보도(/api/closures)를 받지 않는다, 칩을 끄고 켠다", async ({
  page,
}) => {
  const crosswalks: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/closures?")) crosswalks.push(r.url());
  });
  await page.goto(`${HOME}${camera(13)}`);
  await expect(page.getByRole("region", { name: "지도", exact: true })).toHaveAttribute(
    "data-band",
    "area",
  );
  const confirmed = page.getByRole("button", { name: "통제 중 8" });
  await expect(confirmed).toHaveAttribute("aria-pressed", "true");
  await confirmed.click();
  await expect(confirmed).toHaveAttribute("aria-pressed", "false");
  await page.waitForTimeout(800);
  await page.screenshot({ path: "test-results/live-map-area-off.png" });
  await confirmed.click();
  await expect(confirmed).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(800);
  await page.screenshot({ path: "test-results/live-map-area.png" });
  expect(crosswalks).toEqual([]);
});

test("줌 15 부터 횡단보도 — 화면 bbox 로 /api/closures, 그 사건 중심이 bbox 안", async ({
  page,
}) => {
  const crosswalks = page.waitForRequest((r) => r.url().includes("/api/closures?"));
  await page.goto(`${HOME}${camera(15.5)}`);
  await expect(page.getByRole("region", { name: "지도", exact: true })).toHaveAttribute(
    "data-band",
    "crosswalk",
  );
  const [w, s, e, n] = (new URL((await crosswalks).url()).searchParams.get("bbox") ?? "")
    .split(",")
    .map(Number);
  expect([w ?? 0, s ?? 0, e ?? 0, n ?? 0].every(Number.isFinite)).toBe(true);
  expect(Number(lng)).toBeGreaterThan(w ?? 0);
  expect(Number(lng)).toBeLessThan(e ?? 0);
  expect(Number(lat)).toBeGreaterThan(s ?? 0);
  expect(Number(lat)).toBeLessThan(n ?? 0);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "test-results/live-map-crosswalk.png" });
});

test("60초 뒤 같은 at 으로 If-None-Match → 304 — 칩·목록 그대로", async ({ page }) => {
  test.setTimeout(150_000);
  const seen: { status: number; etag: string | null; sent: string | null }[] = [];
  page.on("response", (r) => {
    if (!r.url().includes("/api/closures/events")) return;
    const sent = r.request().headers()["if-none-match"] ?? null;
    seen.push({ status: r.status(), etag: r.headers()["etag"] ?? null, sent });
  });
  await page.goto(HOME);
  await expect.poll(() => seen.length).toBe(1);
  expect(seen[0]?.status).toBe(200);
  expect(seen[0]?.sent).toBeNull();
  await page.waitForTimeout(62_000);
  expect(seen).toHaveLength(2);
  expect(seen[1]?.status).toBe(304);
  expect(seen[1]?.sent).toBe(seen[0]?.etag);
  await expect(page.getByRole("button", { name: "통제 중 8" })).toBeVisible();
  await expect(page.getByRole("region", { name: SHEET })).toContainText(RALLY);
});

test("행을 누르면 사건 카드 — 남은 시간·출처·확신도·근거 원문, 닫으면 목록 (T7.5)", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto(HOME);
  const sheet = page.getByRole("region", { name: SHEET });
  await sheet.getByRole("button", { name: new RegExp(`^${RALLY}`) }).click();
  const card = page.getByRole("article", { name: RALLY });
  await expect(card).toContainText("15:00–16:00");
  await expect(card).toContainText("확인 전"); // 15:00 시작, 공지뿐 — 15:30 에도 예정
  await expect(card).toContainText("경찰청 공지");
  await expect(card).toContainText("보통"); // 확신도 0.75
  await expect(card).toContainText("22곳");
  await card.getByRole("button", { name: "통제 근거 보기" }).click();
  await expect(card).toContainText(EXCERPT);
  await page.waitForTimeout(1200); // 카드를 열면 지도가 그 사건으로
  await page.screenshot({ path: "test-results/live-map-card.png" });
  await card.getByRole("button", { name: "카드 닫기" }).click();
  await expect(sheet.getByRole("region", { name: "통제 중" })).toBeVisible();
  expect(ownErrors(errors)).toEqual([]);
});

test("지도 구역을 누르면 — 겹친 곳은 '여기 통제 N건' 묶음, 하나 고르면 카드 (T7.5)", async ({
  page,
}) => {
  await page.goto(`${HOME}${camera(15.5)}`);
  await expect(page.getByRole("region", { name: "지도", exact: true })).toHaveAttribute(
    "data-band",
    "crosswalk",
  );
  const sheet = page.getByRole("region", { name: SHEET });
  await sheet.getByRole("button", { name: "시트 높이" }).click(); // 접어 지도 가운데를 비운다
  await expect(sheet).toHaveAttribute("data-stage", "collapsed");
  // r04 centroid 는 BE 가 구역 안 대표점으로 준 값(T7.2) — 지도 가운데가 그 점
  const box = await page.locator("canvas.maplibregl-canvas").boundingBox();
  await page.mouse.click(
    (box?.x ?? 0) + (box?.width ?? 0) / 2,
    (box?.y ?? 0) + (box?.height ?? 0) / 2,
  );
  await expect(sheet).toContainText(/여기 통제 \d+건/);
  await expect(sheet).not.toHaveAttribute("data-stage", "collapsed");
  await sheet.getByRole("button", { name: new RegExp(`^${RALLY}`) }).click();
  await expect(page.getByRole("article", { name: RALLY })).toBeVisible();
});

test("?event=<id> 로 열면 그 사건 카드, 지도가 그 사건으로 — 11/9 국회대로 지도 행진 (T7.5)", async ({
  page,
}) => {
  await page.goto("/?t=2026-11-09T13:30:00%2B09:00&event=ccaa9980c6ac");
  const card = page.getByRole("article", { name: "국회의사당앞 → 효자동삼거리 행진" });
  await expect(card).toContainText("15:30 해제 예정");
  await expect(card).toContainText("TOPIS 통제지도");
  await expect(card).toContainText("75곳");
  // 9.5 km 행진 전체가 절반 시트 위에 — 줌 12 아래(구역 대신 고른 사건 윤곽)
  await expect
    .poll(() => Number(new URL(page.url()).hash.split("/")[0]?.slice(5)))
    .toBeLessThan(12);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "test-results/live-map-event.png" });
});
