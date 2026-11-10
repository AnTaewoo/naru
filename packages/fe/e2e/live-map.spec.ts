// T7.4 지금 지도 (ADR-014 A) — iPhone 13 크기. BE 는 사건 v2 기록(scripts/record_live_events.py)과 같은 데이터를
// 워커 발행 경로로 실은 naru_test(경찰청 PDF 3개·코스·공지·TOPIS 공지 6300·TOPIS 통제지도·돌발 11/7·11/9).
// 기대값은 그 기록(data/recorded/naru_api/closure_events_live_1107_1530.json)을 열어 확인한 값
import { devices, expect, test } from "@playwright/test";
import { eventById, recordedLive } from "../src/test/recorded";
import { consoleErrors, fullSheet, ownErrors } from "./helpers";

const iphone = devices["iPhone 13"];
test.use({
  viewport: iphone.viewport,
  deviceScaleFactor: iphone.deviceScaleFactor,
  isMobile: iphone.isMobile,
  hasTouch: iphone.hasTouch,
  userAgent: iphone.userAgent,
});

const HOME = "/?t=2026-11-07T15:30:00%2B09:00";
const SHEET = "서울 통제"; // 기준 시각이 지금이 아니면 — 날짜·시각은 시트 맨 위 기준 줄 (T7.12)
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
  await expect(sheet).toContainText("서울 통제 중 8건, 예정 4건"); // 시각은 맨 위 기준 줄 (T7.12)
  await expect(sheet).toContainText(RALLY);
  await expect(sheet).toContainText("5만 명 · 태평로");
  await expect(sheet).toContainText("15:00–16:00 · 횡단보도 22곳");
  await expect(sheet).not.toContainText("내자");
  await expect(sheet).not.toContainText(EXCERPT); // 원문은 카드의 '통제 근거 보기'에서만 (T5.9·T7.5)
  await expect(sheet).not.toContainText("시각표 기준"); // 데이터 기준 시각 줄은 /licenses 로 (T7.12·T7.13)
  // 이 시각 묶음 (T7.12) — 통제 중 8 + 1시간 안 시작 4. 넓은 창 기록 closure_events_catalog_1107_1530 과 같다
  await expect(sheet.getByRole("region", { name: "이 시각" }).getByRole("button")).toHaveCount(12);
  await expect(page.getByRole("button", { name: "통제 불러오기" })).toHaveCount(0);
  await expect(sheet).toContainText("11월 7일 15:30 기준");
  await expect(sheet.getByRole("button", { name: "지금으로 돌아가기" })).toBeVisible();
  await expect(page.getByRole("button", { name: "지금 시각으로" })).toHaveCount(0); // 시트 안 슬라이더는 끔
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

test("60초 뒤 같은 at 으로 If-None-Match → 304 — 지도 사건·시트 목록(넓은 창) 따로, 칩·목록 그대로", async ({
  page,
}) => {
  test.setTimeout(150_000);
  const seen: { list: boolean; status: number; etag: string | null; sent: string | null }[] = [];
  page.on("response", (r) => {
    if (!r.url().includes("/api/closures/events")) return;
    const list = new URL(r.url()).searchParams.has("from"); // 시트 목록 t 앞뒤 365일 (T7.12)
    const sent = r.request().headers()["if-none-match"] ?? null;
    seen.push({ list, status: r.status(), etag: r.headers()["etag"] ?? null, sent });
  });
  await page.goto(HOME);
  await expect.poll(() => seen.length).toBe(2);
  await page.waitForTimeout(62_000);
  for (const list of [false, true]) {
    const xs = seen.filter((x) => x.list === list);
    expect(xs).toHaveLength(2);
    expect(xs[0]?.status).toBe(200);
    expect(xs[0]?.sent).toBeNull();
    expect(xs[1]?.status).toBe(304);
    expect(xs[1]?.sent).toBe(xs[0]?.etag);
  }
  await expect(page.getByRole("button", { name: "통제 중 8" })).toBeVisible();
  await expect(page.getByRole("region", { name: SHEET })).toContainText(RALLY);
});

test("행을 누르면 사건 카드 — 남은 시간·출처·확신도·근거 원문, 닫으면 목록 (T7.5)", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto(HOME);
  const sheet = page.getByRole("region", { name: SHEET });
  await fullSheet(page, SHEET); // 절반에선 목록이 시트 밖(T7.11 달력으로 슬라이더가 높아졌다)
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
  await expect(sheet.getByRole("region", { name: "이 시각" })).toBeVisible();
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
  // 사건이 와서 구역이 그려진 뒤에 누른다
  await expect(page.getByRole("button", { name: "통제 중 8" })).toBeVisible();
  await page.waitForTimeout(800);
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

test("달력으로 날짜를 바꾸면 그날 같은 시각 — 11/7 07:45 → 3/15 07:45 마라톤 (T7.11)", async ({
  page,
}) => {
  await page.goto("/?t=2026-11-07T07:45:00%2B09:00");
  await page.getByLabel("날짜").fill("2026-03-15");
  // 사건 v2 기록 closure_events_live_0315_0745 — 통제 중 9 · 예정 7
  await expect(page.getByRole("button", { name: "통제 중 9" })).toBeVisible();
  const sheet = page.getByRole("region", { name: SHEET });
  await expect(sheet).toContainText("3월 15일 07:45 기준");
  await expect(sheet).toContainText("마라톤 1구간 세종대로 사거리~숭례문 오거리");
});

test("예시 칩 — 11/9 국회대로 행진을 누르면 11/9 12:00·그 행진 카드, 지도는 행진 전체 (T7.11 → T7.14)", async ({
  page,
}) => {
  await page.goto(HOME);
  const sheet = page.getByRole("region", { name: SHEET });
  const chips = sheet.getByRole("group", { name: "예시로 보기" });
  await chips.getByRole("button", { name: "11/9 국회대로 행진" }).click();
  // TOPIS 통제지도 1109233 ccaa9980c6ac — 12:00 엔 돌발 연결로 통제 중 (T7.3)
  const card = page.getByRole("article", { name: "국회의사당앞 → 효자동삼거리 행진" });
  await expect(card).toContainText("통제 중");
  await expect(sheet).toContainText("11월 9일 12:00 기준");
  // 카드를 열면 사건 범위로(T7.5 ?event= 와 같다) — 9.5 km 행진 전체가 절반 시트 위에, 줌 12 아래는 고른 윤곽
  const zoom = () => Number(new URL(page.url()).hash.split("/")[0]?.slice(5));
  await expect.poll(zoom).toBeLessThan(12);
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "test-results/live-map-example.png" });
});

test("예시 칩은 시트를 접어도 보인다 — 3/15 서울마라톤 → 3/15 07:45·1구간 카드 (T7.14)", async ({
  page,
}) => {
  await page.goto(HOME);
  const sheet = page.getByRole("region", { name: SHEET });
  await sheet.getByRole("button", { name: "시트 높이" }).click(); // 절반 → 접힘
  await expect(sheet).toHaveAttribute("data-stage", "collapsed");
  await page.waitForTimeout(500); // 높이 전환(200ms)이 끝난 뒤 잰다 — 접힌 시트 96px
  const chip = sheet
    .getByRole("group", { name: "예시로 보기" })
    .getByRole("button", { name: "3/15 서울마라톤" });
  const c = await chip.boundingBox();
  const s = await sheet.boundingBox();
  expect(c).not.toBeNull();
  expect(s?.height).toBe(96);
  expect((c?.y ?? 0) + (c?.height ?? 0)).toBeLessThanOrEqual((s?.y ?? 0) + (s?.height ?? 0));
  await page.screenshot({ path: "test-results/live-map-collapsed-chips.png" });
  await chip.click();
  await expect(
    page.getByRole("article", { name: "마라톤 1구간 세종대로 사거리~숭례문 오거리" }),
  ).toBeVisible();
  await expect(sheet).toContainText("3월 15일 07:45 기준");
});

test("11/8 12:00 그 시각 통제 없음 — 한 줄 + 내일·지난 통제, 지난 행 → 그 시작 시각·카드·지도, 지금으로 돌아가기 (T7.12)", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto("/?t=2026-11-08T12:00:00%2B09:00");
  const sheet = page.getByRole("region", { name: SHEET });
  // 넓은 창 기록 closure_events_catalog_1108_1200 — 이 시각 0 · 내일(11/9) 다섯 · 지난 28
  await expect(sheet).toContainText("11월 8일 12:00 기준");
  await expect(sheet.getByRole("region", { name: "이 시각" })).toContainText(
    "이 시각 서울에 걸린 통제가 없어요",
  );
  // 빈 안내 밑에 예시를 크게 한 번 더 (T7.14)
  await expect(
    sheet
      .getByRole("region", { name: "이 시각" })
      .getByRole("group", { name: "예시로 보기" })
      .getByRole("button"),
  ).toHaveCount(3);
  await fullSheet(page, SHEET);
  const upcoming = sheet.getByRole("region", { name: "다가오는 통제" });
  await expect(upcoming.getByRole("group", { name: "내일" }).getByRole("button")).toHaveCount(5);
  const past = sheet.getByRole("region", { name: "지난 통제" });
  await expect(
    past.getByRole("button", { name: /^의사당역 5번출구 → 민주당사 행진/ }),
  ).toContainText("11월 7일"); // 11/7 19:00 끝 — 가장 최근
  await page.screenshot({ path: "test-results/live-map-sections.png" });
  await past.getByRole("button", { name: "더 보기 (23)" }).click();
  await past.getByRole("button", { name: new RegExp(`^${RALLY}`) }).click();
  // 경찰청 r04 15:00 시작으로 — 카드 위에도 기준 줄, 지도는 그 구역(첫 화면 맞춤 13 보다 가깝게)
  await expect(page.getByRole("article", { name: RALLY })).toContainText("15:00–16:00");
  await expect(sheet).toContainText("11월 7일 15:00 기준");
  const zoom = () => Number(new URL(page.url()).hash.split("/")[0]?.slice(5));
  await expect.poll(zoom).toBeGreaterThan(13);
  await page.waitForTimeout(1200);
  await page.screenshot({ path: "test-results/live-map-past-card.png" });
  await sheet.getByRole("button", { name: "지금으로 돌아가기" }).click();
  await expect(page.getByRole("region", { name: "지금 서울 통제" })).toBeVisible();
  await expect(page.getByRole("button", { name: "지금으로 돌아가기" })).toHaveCount(0);
  expect(ownErrors(errors)).toEqual([]);
});
