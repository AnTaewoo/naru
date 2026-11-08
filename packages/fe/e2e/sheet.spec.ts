// T5.6 하단 시트 + 지도 맞춤 — iPhone 13 크기(보이는 영역 390×664). 경로·통제 입력은 recorded naru_api 와 같은 DB:
// route_0745 질의(교보빌딩 앞 → 대한문), closure_events 의 3/15 1구간(07:20~08:08, 횡단보도 6곳)
import { devices, expect, test } from "@playwright/test";
import { recorded } from "../src/test/recorded";
import { consoleErrors, ownErrors } from "./helpers";

const iphone = devices["iPhone 13"];
test.use({
  viewport: iphone.viewport,
  deviceScaleFactor: iphone.deviceScaleFactor,
  isMobile: iphone.isMobile,
  hasTouch: iphone.hasTouch,
  userAgent: iphone.userAgent,
});

const q = recorded("route_0745").query ?? {};
const od = `from=${q["from"] ?? ""}&to=${q["to"] ?? ""}`;
const SEG1 = /마라톤 1구간 세종대로 사거리~숭례문 오거리/;

test("경로를 찾으면 시트가 접히고(96px) 출발·도착 핀이 시트 위 화면 안에 보인다, 푸터 없음", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto(`/?t=2026-03-15T07:45:00+09:00&${od}`);
  const sheet = page.getByRole("region", { name: "길찾기 결과" });
  await expect(page.getByRole("article", { name: "가장 빠른 길" })).toContainText("12분");
  await expect(sheet).toHaveAttribute("data-stage", "collapsed");
  await page.waitForTimeout(2000); // 화면 맞춤 애니메이션·타일
  const box = await sheet.boundingBox();
  expect(Math.round(box?.height ?? 0)).toBe(96);
  for (const name of ["출발 지점", "도착 지점"]) {
    const pin = await page.getByRole("img", { name }).boundingBox();
    expect(pin).not.toBeNull();
    expect(pin?.y ?? -1).toBeGreaterThan(0);
    expect((pin?.y ?? 0) + (pin?.height ?? 0)).toBeLessThanOrEqual(box?.y ?? 0);
  }
  await expect(page.getByRole("contentinfo")).toBeHidden(); // 모바일 푸터 숨김 (고지는 지도 출처 칸)
  await expect(page.getByRole("status", { name: "지도 불러오는 중" })).toHaveCount(0);
  await page.screenshot({ path: "test-results/iphone13-t56-route.png" });
  expect(ownErrors(errors)).toEqual([]);
});

test("손잡이 — 탭은 접힘↔절반, 위로 끌면 전체, 아래로 끌면 접힘, 끌어도 글자가 선택되지 않는다", async ({
  page,
}) => {
  await page.goto(`/?t=2026-03-15T07:45:00+09:00&${od}`);
  const sheet = page.getByRole("region", { name: "길찾기 결과" });
  await expect(sheet).toHaveAttribute("data-stage", "collapsed");
  const grip = sheet.getByRole("button", { name: "시트 높이" });
  await grip.click();
  await expect(sheet).toHaveAttribute("data-stage", "half");
  // 높이 전환(200ms)이 끝난 뒤 끈다 — 끌기는 지금 보이는 높이에서 시작한다
  const settled = async (px: number) =>
    expect.poll(async () => Math.round((await sheet.boundingBox())?.height ?? 0)).toBe(px);
  await settled(332); // iPhone 13 보이는 높이 664 의 절반
  const drag = async (dy: number) => {
    const b = await grip.boundingBox();
    const x = (b?.x ?? 0) + (b?.width ?? 0) / 2;
    const y = (b?.y ?? 0) + (b?.height ?? 0) / 2;
    await page.mouse.move(x, y);
    await page.mouse.down();
    await page.mouse.move(x, y + dy, { steps: 12 });
    await page.mouse.up();
  };
  await drag(-250); // 절반(332) → 582 쯤 → 전체(664 − 출발·도착 패널 176 = 488)
  await expect(sheet).toHaveAttribute("data-stage", "full");
  expect(await page.evaluate(() => window.getSelection()?.toString() ?? "")).toBe("");
  await settled(488); // 손잡이가 패널 아래에 있어 다시 잡을 수 있다
  await drag(450); // 전체 → 38 → 접힘(96)
  await expect(sheet).toHaveAttribute("data-stage", "collapsed");
});

test("통제를 불러오면 시트가 접히고 지도가 그 통제 범위로 — 서울 전체로 줌아웃하지 않는다", async ({
  page,
}) => {
  const closuresUrls: string[] = [];
  page.on("request", (r) => {
    if (r.url().includes("/api/closures?")) closuresUrls.push(r.url());
  });
  const eventsRes = page.waitForResponse((r) => r.url().includes("/api/closures/events"));
  await page.goto("/");
  const events = (await (await eventsRes).json()) as {
    events: { reason: string; bbox: number[] }[];
  };
  const seg1 = events.events.find((e) => e.reason.includes("1구간"));
  expect(seg1).toBeDefined();
  const empty = page.getByText("이 시각에 걸린 통제가 없어요.");
  await empty.getByRole("button", { name: "통제 불러오기" }).click();
  await page
    .getByRole("region", { name: "통제 불러오기" })
    .getByRole("button", { name: SEG1 })
    .click();
  const sheet = page.getByRole("region", { name: "3월 15일 통제" });
  await expect(sheet).toHaveAttribute("data-stage", "collapsed");
  await page.waitForTimeout(2500); // 화면 맞춤 → moveend → 그 범위로 /api/closures
  const last = new URL(closuresUrls.at(-1) ?? "http://x/").searchParams.get("bbox") ?? "";
  const [w, s, e, n] = last.split(",").map(Number);
  const [ew, es, ee, en] = seg1?.bbox ?? [];
  // 지도가 그 통제 횡단보도 전체를 담고(bbox 포함), 서울 전체가 아니다(가로 0.1° ≈ 9 km 미만)
  expect(w).toBeLessThanOrEqual(ew ?? 0);
  expect(s).toBeLessThanOrEqual(es ?? 0);
  expect(e).toBeGreaterThanOrEqual(ee ?? 0);
  expect(n).toBeGreaterThanOrEqual(en ?? 0);
  expect((e ?? 0) - (w ?? 0)).toBeLessThan(0.1);
});
