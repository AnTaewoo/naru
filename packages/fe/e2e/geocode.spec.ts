// T5.8 주소·검색 — iPhone 13 크기. BE 는 카카오 기록 재생(NARU_GEOCODE_SOURCE=recorded)으로 띄운다:
// 검색 '교보빌딩' 1위 광화문교보빌딩·'덕수궁' 3위 덕수궁 대한문(= recorded route_0745 출발·도착),
// 주소 교보빌딩 "종로구 종로 1"·대한문 "중구 세종대로 99". 기록에 없는 요청은 503 → 화면은 대체 문구.
// T7.14 — 홈 검색 줄을 누르면 지도 이동(줌 17)·이름 핀·장소 카드([출발][도착][☆ 저장]), 칸 검색도 지도 이동
import { devices, expect, test, type Page } from "@playwright/test";
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
const T = "t=2026-03-15T07:45:00+09:00";

async function tapMap(page: Page, fx: number, fy: number) {
  const canvas = page.locator("canvas.maplibregl-canvas");
  const box = await canvas.boundingBox();
  await canvas.click({ position: { x: (box?.width ?? 0) * fx, y: (box?.height ?? 0) * fy } });
}

test("홈 검색 '교보빌딩' → 출발, 도착 칸 '덕수궁' → 대한문 → recorded route_0745 와 같은 12분 길", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  // 지도 가운데를 기록할 때의 near(FE 기본 중심 37.5675,126.9775, MANIFEST T5.8)로 고정 — 첫 화면은 그 시각
  // 사건 범위로 맞춰지니(T7.4) 카메라를 주소(#map=)로 준다
  await page.goto(`/?${T}#map=15/37.5675/126.9775`);
  await expect(page.getByRole("region", { name: "지도", exact: true })).toHaveAttribute(
    "data-band",
    "crosswalk",
  );
  const searched = page.waitForRequest((r) => r.url().includes("/api/geocode/search"));
  await page.getByRole("searchbox", { name: "장소·주소 검색" }).fill("교보빌딩");
  const near = new URL((await searched).url()).searchParams.get("near") ?? "";
  // near = 지도 가운데 — BE 가 소수 2자리로 맞춘 값이 기록할 때와 같다 (37.57, 126.98)
  expect(near.split(",").map((x) => Number(x).toFixed(2))).toEqual(["37.57", "126.98"]);
  const results = page.getByRole("list", { name: "검색 결과" });
  await expect(results.getByRole("listitem")).toHaveCount(10);
  // 줄마다 지도 가운데부터 거리 (T7.14) — 광화문교보빌딩 387m (측지선 386.6 m)
  await expect(results.getByRole("listitem").first()).toContainText("387m");
  // 줄을 누르면 그 장소 — 지도는 줌 17 로 그리로, 이름 핀, 시트는 장소 카드 (T7.14)
  await page.getByRole("button", { name: "광화문교보빌딩 서울 종로구 종로 1" }).click();
  await expect(page.getByRole("img", { name: "광화문교보빌딩 위치" })).toBeVisible();
  const card = page.getByRole("article", { name: "광화문교보빌딩" });
  await expect(card).toContainText("서울 종로구 종로 1");
  const zoom = () => Number(new URL(page.url()).hash.split("/")[0]?.slice(5));
  await expect.poll(zoom).toBeGreaterThan(16.9);
  await page.waitForTimeout(800);
  await page.screenshot({ path: "test-results/iphone13-t714-place.png" });
  await card.getByRole("button", { name: "출발" }).click();
  await expect(page.getByRole("button", { name: "출발 광화문교보빌딩" })).toBeVisible();
  await expect(page.getByRole("img", { name: "광화문교보빌딩 위치" })).toHaveCount(0); // 출발 핀으로
  await page.getByRole("button", { name: "도착 지도를 눌러 도착을 고르세요" }).click();
  await page.getByRole("searchbox", { name: "도착 검색" }).fill("덕수궁");
  await expect(
    page.getByRole("button", { name: "덕수궁 대한문 서울 중구 세종대로 99" }),
  ).toBeVisible();
  await page.screenshot({ path: "test-results/iphone13-t58-search.png" });
  await page.getByRole("button", { name: "덕수궁 대한문 서울 중구 세종대로 99" }).click();
  await expect(page.getByRole("button", { name: "도착 덕수궁 대한문" })).toBeVisible();
  await expect(page.getByRole("article", { name: "가장 빠른 길" })).toContainText("12분");
  await page.waitForTimeout(2000); // 지도 맞춤·타일
  await page.screenshot({ path: "test-results/iphone13-t58-route.png" });
  expect(ownErrors(errors)).toEqual([]);
});

test("검색한 장소 핀은 카드를 닫거나·지도를 누르거나·다른 곳을 검색하면 사라진다, ☆ 저장은 빈 검색칸에 (T7.14)", async ({
  page,
}) => {
  await page.goto(`/?${T}#map=15/37.5675/126.9775`);
  const box = page.getByRole("searchbox", { name: "장소·주소 검색" });
  const pick = async () => {
    await box.fill("교보빌딩");
    await page.getByRole("button", { name: "광화문교보빌딩 서울 종로구 종로 1" }).click();
    await expect(page.getByRole("img", { name: "광화문교보빌딩 위치" })).toBeVisible();
  };
  const pin = page.getByRole("img", { name: "광화문교보빌딩 위치" });
  await pick();
  await page.getByRole("button", { name: "장소 닫기" }).click();
  await expect(pin).toHaveCount(0);
  await pick();
  await page.waitForTimeout(1200); // 줌 17 이동이 끝난 뒤
  await tapMap(page, 0.15, 0.3);
  await expect(pin).toHaveCount(0);
  await pick();
  await page.getByRole("button", { name: "☆ 저장" }).click();
  await expect(page.getByRole("button", { name: "★ 저장됨" })).toBeVisible();
  await box.fill("덕수");
  await expect(pin).toHaveCount(0);
  await box.fill("");
  await box.blur();
  await box.focus();
  const saved = page.getByRole("list", { name: "저장한 장소" });
  await expect(saved).toContainText("광화문교보빌딩");
  await saved.getByRole("button", { name: "광화문교보빌딩 서울 종로구 종로 1" }).click();
  await expect(pin).toBeVisible();
});

test("출발·도착 칸 검색으로 고른 곳도 지도가 그리로(줌 17) — 출발 교보빌딩 (T7.14)", async ({
  page,
}) => {
  await page.goto(`/?${T}#map=15/37.5675/126.9775`);
  await page.getByRole("button", { name: "길찾기" }).click();
  await page.getByRole("button", { name: /^출발 / }).click();
  await page.getByRole("searchbox", { name: "출발 검색" }).fill("교보빌딩");
  await page.getByRole("button", { name: "광화문교보빌딩 서울 종로구 종로 1" }).click();
  await expect(page.getByRole("button", { name: "출발 광화문교보빌딩" })).toBeVisible();
  await expect(page.getByRole("img", { name: "출발 지점" })).toBeVisible();
  const zoom = () => Number(new URL(page.url()).hash.split("/")[0]?.slice(5));
  await expect.poll(zoom).toBeGreaterThan(16.9);
});

test("주소창 출발·도착 → 칸에 도로명 주소, 좌표는 안 보인다", async ({ page }) => {
  await page.goto(`/?${T}&from=${q["from"] ?? ""}&to=${q["to"] ?? ""}`);
  await expect(page.getByRole("button", { name: "출발 종로구 종로 1" })).toBeVisible();
  await expect(page.getByRole("button", { name: "도착 중구 세종대로 99" })).toBeVisible();
  const panel = page.getByRole("region", { name: "출발·도착" });
  await expect(panel).not.toContainText(/\d+\.\d{4}/);
});

test("지도를 누른 점은 주소 — 기록에 없는 점이면 '선택한 위치', 입력 중 지도를 누르면 그 칸", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto(`/?${T}&from=${q["from"] ?? ""}&to=${q["to"] ?? ""}`);
  await expect(page.getByRole("button", { name: "도착 중구 세종대로 99" })).toBeVisible();
  await page.getByRole("button", { name: "도착 중구 세종대로 99" }).click();
  await expect(page.getByRole("searchbox", { name: "도착 검색" })).toBeVisible();
  await page.waitForTimeout(1500); // 경로 맞춤이 끝난 뒤 누른다
  await tapMap(page, 0.5, 0.4);
  await expect(page.getByRole("searchbox")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "도착 선택한 위치" })).toBeVisible();
  await expect(page.getByRole("button", { name: "출발 종로구 종로 1" })).toBeVisible();
  expect(ownErrors(errors)).toEqual([]);
});

test("기록에 없는 검색어는 '검색을 못 했어요' (BE 503 geocode_unavailable)", async ({ page }) => {
  await page.goto(`/?${T}`);
  await page.getByRole("searchbox", { name: "장소·주소 검색" }).fill("잠실역");
  await expect(page.getByText("검색을 못 했어요")).toBeVisible();
  await page.getByRole("button", { name: "닫기" }).click();
  await expect(page.getByRole("searchbox", { name: "장소·주소 검색" })).toHaveValue("");
});
