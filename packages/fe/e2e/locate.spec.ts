// T5.7 내 위치 — iPhone 13 크기(보이는 영역 390×664). 위치는 Playwright 위치 권한으로 넣는다(실데이터 좌표):
// 교보빌딩 = recorded route_0745 출발(카카오 24020019), 잠실 = recorded error_out_of_coverage 출발(태우 실서버 요청).
// 보행망 범위 = /closures/events 의 coverage (recorded closure_events 와 같은 그래프)
import { devices, expect, test, type BrowserContext, type Page } from "@playwright/test";
import { recorded } from "../src/test/recorded";
import { consoleErrors, denyGeolocation, ownErrors } from "./helpers";

const iphone = devices["iPhone 13"];
test.use({
  viewport: iphone.viewport,
  deviceScaleFactor: iphone.deviceScaleFactor,
  isMobile: iphone.isMobile,
  hasTouch: iphone.hasTouch,
  userAgent: iphone.userAgent,
});

const q = recorded("route_0745").query ?? {};
function geo(latLng: string | undefined) {
  const [latitude = Number.NaN, longitude = Number.NaN] = (latLng ?? "").split(",").map(Number);
  return { latitude, longitude };
}
const KYOBO = geo(q["from"]);
const JAMSIL = geo(recorded("error_out_of_coverage").query?.["from"]);
const T = "t=2026-03-15T07:45:00+09:00";

async function locatedAt(context: BrowserContext, where: { latitude: number; longitude: number }) {
  await context.grantPermissions(["geolocation"]);
  await context.setGeolocation(where);
}

/** 범위(coverage)를 받은 뒤에 시작한다 — 받기 전에 온 위치는 범위를 모르니 그대로 넣는다 */
async function gotoAfterCoverage(page: Page, query: string) {
  const events = page.waitForResponse((r) => r.url().includes("/api/closures/events"));
  await page.goto(`/?${query}`);
  expect((await events).status()).toBe(200);
}

async function tapMap(page: Page, fx: number, fy: number) {
  const canvas = page.locator("canvas.maplibregl-canvas");
  const box = await canvas.boundingBox();
  await canvas.click({ position: { x: (box?.width ?? 0) * fx, y: (box?.height ?? 0) * fy } });
}

test("도착은 주소창(대한문), 출발 칸 옆 '내 위치' → 교보빌딩에서 recorded route_0745 와 같은 12분 길", async ({
  page,
  context,
}) => {
  const errors = consoleErrors(page);
  await locatedAt(context, KYOBO);
  await gotoAfterCoverage(page, `${T}&to=${q["to"] ?? ""}`);
  // 주소로 들어오면 찾지 않는다 — 누를 때만
  await expect(
    page.getByRole("button", { name: "출발 지도를 눌러 출발을 고르세요" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "출발을 내 위치로" }).click();
  await expect(page.getByRole("button", { name: "출발 내 위치" })).toBeVisible();
  await expect(page.getByRole("article", { name: "가장 빠른 길" })).toContainText("12분");
  await expect(page.getByRole("button", { name: "출발을 내 위치로" })).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await page.waitForTimeout(2000); // 지도 맞춤·타일
  await page.screenshot({ path: "test-results/iphone13-t57-locate.png" });
  expect(ownErrors(errors)).toEqual([]);
});

test("길찾기를 켜면 출발은 내 위치(교보빌딩) — 지도를 한 번 누르면 도착, 경로", async ({
  page,
  context,
}) => {
  const errors = consoleErrors(page);
  await locatedAt(context, KYOBO);
  await gotoAfterCoverage(page, T);
  await page.getByRole("button", { name: "길찾기" }).click();
  await expect(page.getByRole("button", { name: "출발 내 위치" })).toBeVisible();
  await expect(page.getByRole("img", { name: "출발 지점" })).toBeVisible();
  await page.waitForTimeout(1000); // 내 위치로 옮기는 중
  await tapMap(page, 0.3, 0.4); // 출발·도착 패널(108px) 아래, 절반 시트(332px) 위
  await expect(page.getByRole("img", { name: "도착 지점" })).toBeVisible();
  await expect(page.getByRole("article", { name: "가장 빠른 길" })).toBeVisible();
  expect(ownErrors(errors)).toEqual([]);
});

test("범위 밖 — 잠실이면 출발 칸은 비우고 안내, 지도로 고르면 안내가 사라진다", async ({
  page,
  context,
}) => {
  await locatedAt(context, JAMSIL);
  await gotoAfterCoverage(page, T);
  await page.getByRole("button", { name: "길찾기" }).click();
  const note = page.getByText(
    "내 위치가 길찾기 범위(종로·중구) 밖이에요. 지도를 눌러 출발을 고르세요",
  );
  await expect(note).toBeVisible();
  await expect(
    page.getByRole("button", { name: "출발 지도를 눌러 출발을 고르세요" }),
  ).toBeVisible();
  await expect(page.getByRole("img", { name: "출발 지점" })).toHaveCount(0);
  await tapMap(page, 0.3, 0.4);
  await expect(page.getByRole("img", { name: "출발 지점" })).toBeVisible();
  await expect(note).toHaveCount(0);
});

test("거부 — 위치 권한이 꺼져 있으면 안내하고 지도로 고른다", async ({ page, browser }) => {
  await gotoAfterCoverage(page, T);
  const cdp = await denyGeolocation(browser, page);
  await expect
    .poll(() =>
      page.evaluate(async () => (await navigator.permissions.query({ name: "geolocation" })).state),
    )
    .toBe("denied");
  await page.getByRole("button", { name: "길찾기" }).click();
  await expect(
    page.getByText("위치 권한이 꺼져 있어요. 지도를 눌러 출발을 고르세요"),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "출발 지도를 눌러 출발을 고르세요" }),
  ).toBeVisible();
  await tapMap(page, 0.3, 0.4);
  await expect(page.getByRole("img", { name: "출발 지점" })).toBeVisible();
  await cdp.detach();
});

test("지도 '내 위치 찾기'(GeolocateControl) — 교보빌딩이면 파란 점, 컨트롤 이름은 한국어", async ({
  page,
  context,
}) => {
  const errors = consoleErrors(page);
  await locatedAt(context, KYOBO);
  await gotoAfterCoverage(page, T);
  await expect(page.getByRole("button", { name: "확대" })).toBeVisible();
  await expect(page.getByRole("button", { name: "축소" })).toBeVisible();
  await page.getByRole("button", { name: "내 위치 찾기" }).click();
  await expect(page.locator(".maplibregl-user-location-dot")).toBeVisible();
  await expect(page.getByText("길찾기 범위(종로·중구) 밖")).toHaveCount(0);
  expect(ownErrors(errors)).toEqual([]);
});

test("지도 '내 위치 찾기' — 잠실이면 길찾기 범위 밖이라고 잠깐 안내", async ({ page, context }) => {
  await locatedAt(context, JAMSIL);
  await gotoAfterCoverage(page, T);
  await page.getByRole("button", { name: "내 위치 찾기" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "길찾기 범위(종로·중구) 밖" }),
  ).toBeVisible();
});
