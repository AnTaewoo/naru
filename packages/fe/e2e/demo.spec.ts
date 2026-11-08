// 시연 흐름 (ROADMAP T5.3): 교보빌딩 앞 → 대한문, 통제 중 시각을 고르면 지하보도로 건너는 우회와 지하보도 레그.
// 출발·도착은 recorded naru_api/route_0745.json 을 기록할 때 보낸 질의 그대로. 13:35 는 통제가 다 끝난 시각
// (같은 기록의 /closures 창이 가장 늦게 10:41 에 끝난다), 슬라이더 "10분 전" 35번 = 07:45 (recorded 와 같은 시각)
import { expect, test } from "@playwright/test";
import { recorded } from "../src/test/recorded";
import { consoleErrors, expandSheet, ownErrors } from "./helpers";

const q = recorded("route_0745").query ?? {};
const od = `from=${q["from"] ?? ""}&to=${q["to"] ?? ""}`;

test("시연 — 통제 끝난 13:35 에서 슬라이더로 07:45 → 지하보도 우회, 경로 상세에 지하보도 레그", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto(`/?t=2026-03-15T13:35:00+09:00&${od}`);
  // 13:35 응답 = recorded route_1330 과 같은 674 s·808.3 m·피한 곳 0 (2026-11-08 make dev Flask 에 GET 으로 확인)
  await expect(page.getByRole("article", { name: "가장 빠른 길" })).toContainText("11분");
  await expect(page.getByText("이 시각엔 경로에 걸린 통제가 없어요.")).toBeVisible();
  await expect(page.getByRole("article", { name: "원래 길" })).toHaveCount(0);
  await expandSheet(page, "길찾기 결과"); // 경로가 오면 시트가 접힌다(T5.6) — 펼쳐서 슬라이더
  const back = page.getByRole("button", { name: "10분 전" });
  for (let k = 0; k < 35; k++) await back.click();
  await expect(page.getByText("07:45", { exact: true })).toBeVisible();
  const fast = page.getByRole("article", { name: "가장 빠른 길" });
  await expect(fast).toContainText("12분");
  await expect(fast).toContainText("840m · 07:57 도착");
  await expect(page.getByRole("article", { name: "원래 길" })).toContainText("지금 못 감");
  await page.getByRole("button", { name: "경로 상세" }).click();
  const underpass = page
    .getByRole("list", { name: "경로 상세" })
    .getByRole("listitem")
    .filter({ hasText: "광화문(세종문화회관) 지하보도" });
  await expect(underpass).toContainText("156m");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "test-results/demo-0745.png" });
  expect(ownErrors(errors)).toEqual([]);
});
