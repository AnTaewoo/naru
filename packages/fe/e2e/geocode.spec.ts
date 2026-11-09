// T5.8 주소·검색 — iPhone 13 크기. BE 는 카카오 기록 재생(NARU_GEOCODE_SOURCE=recorded)으로 띄운다:
// 검색 '교보빌딩' 1위 광화문교보빌딩·'덕수궁' 3위 덕수궁 대한문(= recorded route_0745 출발·도착),
// 주소 교보빌딩 "종로구 종로 1"·대한문 "중구 세종대로 99". 기록에 없는 요청은 503 → 화면은 대체 문구
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
  await page.getByRole("button", { name: "광화문교보빌딩 출발" }).click();
  await expect(page.getByRole("button", { name: "출발 광화문교보빌딩" })).toBeVisible();
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
