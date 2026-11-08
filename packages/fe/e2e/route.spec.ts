// 길찾기 끝에서 끝으로 — 실제 Flask(/route) + Next. 출발·도착은 recorded naru_api/route_0745.json 을 기록할 때
// 보낸 질의 그대로(교보빌딩 앞 → 대한문). 카드 숫자는 그 recorded 응답과 같아야 한다 (같은 DB·같은 BE 커밋)
import { expect, test } from "@playwright/test";
import { recorded } from "../src/test/recorded";
import { consoleErrors, expandSheet, expectAttributionUncovered, ownErrors } from "./helpers";

const q = recorded("route_0745").query ?? {};
const od = `from=${q["from"] ?? ""}&to=${q["to"] ?? ""}`;

test("길찾기 07:45 — 지하보도로 건너는 경로, 원래 길 막힘, 핀, 경로 상세·통제 근거", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto(`/?t=2026-03-15T07:45:00+09:00&${od}`);
  const fast = page.getByRole("article", { name: "가장 빠른 길" });
  await expect(fast).toContainText("12분");
  await expect(fast).toContainText("840m · 07:57 도착");
  await expect(fast).toContainText("지하보도 1");
  await expect(page.getByRole("article", { name: "원래 길" })).toContainText("지금 못 감");
  await expect(
    page.getByText(/광화문\(세종문화회관\) 지하보도로 건너는 길을 골랐어요/),
  ).toBeVisible();
  await expect(page.getByRole("img", { name: "출발 지점" })).toBeVisible();
  await expect(page.getByRole("img", { name: "도착 지점" })).toBeVisible();
  // 출발·도착 패널이 위를 덮어도 타일 출처는 가리지 않는다
  await expectAttributionUncovered(page);
  await page.waitForTimeout(2500); // 화면 맞춤·타일 (스크린샷용)
  await page.screenshot({ path: "test-results/route-0745.png" });
  await expandSheet(page, "길찾기 결과"); // 경로가 오면 시트가 접힌다(T5.6)
  await page.getByRole("button", { name: "경로 상세" }).click();
  await expect(page.getByRole("list", { name: "경로 상세" }).getByRole("listitem")).toHaveCount(7);
  await page.getByRole("button", { name: "통제 근거" }).click();
  await expect(page.getByRole("region", { name: "통제 근거" })).toContainText("확신도");
  await page.screenshot({ path: "test-results/route-0745-evidence.png" });
  expect(ownErrors(errors)).toEqual([]);
});

test("길찾기 13:30 — 통제가 끝나 원래 길 그대로, 걸린 통제 없음", async ({ page }) => {
  const errors = consoleErrors(page);
  await page.goto(`/?t=2026-03-15T13:30:00+09:00&${od}`);
  await expect(page.getByRole("article", { name: "가장 빠른 길" })).toContainText("11분");
  await expect(page.getByText("이 시각엔 경로에 걸린 통제가 없어요.")).toBeVisible();
  await expect(page.getByRole("article", { name: "원래 길" })).toHaveCount(0);
  expect(ownErrors(errors)).toEqual([]);
});

test("홈 → 길찾기 → 지도를 두 번 눌러 출발·도착 → 경로 카드, 뒤로 → 홈", async ({ page }) => {
  const errors = consoleErrors(page);
  await page.goto("/?t=2026-03-15T07:45:00+09:00");
  await page.getByRole("button", { name: "길찾기" }).click();
  await expect(page.getByText("지도를 눌러 출발을 고르세요")).toBeVisible();
  const canvas = page.locator("canvas.maplibregl-canvas");
  await expect(canvas).toBeVisible();
  const box = await canvas.boundingBox();
  const w = box?.width ?? 0;
  const h = box?.height ?? 0;
  await canvas.click({ position: { x: w * 0.4, y: h * 0.35 } });
  await expect(page.getByRole("img", { name: "출발 지점" })).toBeVisible();
  await canvas.click({ position: { x: w * 0.6, y: h * 0.45 } });
  await expect(page.getByRole("img", { name: "도착 지점" })).toBeVisible();
  await expect(page.getByRole("article", { name: "가장 빠른 길" })).toBeVisible();
  await page.getByRole("button", { name: "뒤로" }).click();
  // 홈으로 — 기준 시각이 3/15 라 시트 제목은 날짜(T5.4). 길찾기 바가 다시 보이면 홈이다
  await expect(page.getByRole("button", { name: "길찾기" })).toBeVisible();
  await expect(page.getByRole("img", { name: "출발 지점" })).toHaveCount(0);
  expect(ownErrors(errors)).toEqual([]);
});
