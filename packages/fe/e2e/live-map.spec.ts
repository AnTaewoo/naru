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
  const sheet = page.getByRole("region", { name: "11월 7일 통제" });
  await expect(sheet).toContainText("15:30 기준 · 서울 통제 중 8건, 예정 4건");
  await expect(sheet).toContainText(RALLY);
  await expect(sheet).toContainText("5만 명 · 태평로");
  await expect(sheet).toContainText("15:00–16:00 · 횡단보도 22곳");
  await expect(sheet).not.toContainText("내자");
  await expect(sheet).not.toContainText(EXCERPT); // 원문은 '공지 원문 보기'에서만 (T5.9)
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
  await expect(page.getByRole("region", { name: "11월 7일 통제" })).toContainText(RALLY);
});
