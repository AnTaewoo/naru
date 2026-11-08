// 통제 불러오기 (T5.4, ADR-010): 지금(통제 0건)에서 DB 의 통제를 불러와 그 시각·그 장소로 간다.
// 사건 목록 = recorded naru_api/closure_events.json 과 같은 개발 DB(11/7 집회 2, 3/15 마라톤 5).
// 07:20 경로 = 2026-11-08 공개 주소 /api/route 로 확인한 700 s·839.6 m·피한 2곳(확인)·광화문(세종문화회관)
// 지하보도 (07:45 기록과 같다). "지금"에 통제가 없는 날에만 성립한다 (2026-11-08 기준 지금 통제 0건)
import { expect, test } from "@playwright/test";
import { recorded } from "../src/test/recorded";
import { consoleErrors, ownErrors } from "./helpers";

const q = recorded("route_0745").query ?? {};
const od = `from=${q["from"] ?? ""}&to=${q["to"] ?? ""}`;
const SEG1 = /마라톤 1구간 세종대로 사거리~숭례문 오거리/;

test("홈 — 지금(통제 없음) → 빈 칸 안내 → 3/15 1구간 → 07:20 통제가 보인다 → '지금'", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto("/");
  await expect(page.getByText("오늘 통제", { exact: true })).toBeVisible();
  const empty = page.getByText("이 시각에 걸린 통제가 없어요.");
  await empty.getByRole("button", { name: "통제 불러오기" }).click();
  const list = page.getByRole("region", { name: "통제 불러오기" });
  await expect(list.getByText("11월 7일 (토)")).toBeVisible();
  await expect(list.getByText("3월 15일 (일)")).toBeVisible();
  await list.getByRole("button", { name: SEG1 }).click();
  await expect(page.getByText("07:20", { exact: true })).toBeVisible();
  await expect(page.getByText("3월 15일 통제", { exact: true })).toBeVisible();
  await expect(page.getByText(/횡단보도 \d+곳 통제 중/)).toBeVisible();
  await page.waitForTimeout(2000); // 지도 맞춤·타일 (스크린샷용)
  await page.screenshot({ path: "test-results/events-0720.png" });
  await page.getByRole("button", { name: "지금 시각으로" }).click();
  await expect(page.getByText("오늘 통제", { exact: true })).toBeVisible();
  expect(ownErrors(errors)).toEqual([]);
});

test("길찾기 — 지금은 걸린 통제 없음 → 통제 불러오기 → 1구간(07:20) → 지하보도 우회, 원래 길 지금 못 감", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto(`/?${od}`);
  const note = page.getByText("이 시각엔 경로에 걸린 통제가 없어요.");
  await note.getByRole("button", { name: "통제 불러오기" }).click();
  await page
    .getByRole("region", { name: "통제 불러오기" })
    .getByRole("button", { name: SEG1 })
    .click();
  await expect(page.getByText("07:20", { exact: true })).toBeVisible();
  const fast = page.getByRole("article", { name: "가장 빠른 길" });
  await expect(fast).toContainText("12분");
  await expect(fast).toContainText("840m · 07:32 도착");
  await expect(fast).toContainText("지하보도 1");
  await expect(page.getByRole("article", { name: "원래 길" })).toContainText("지금 못 감");
  await page.waitForTimeout(1500);
  await page.screenshot({ path: "test-results/events-route-0720.png" });
  expect(ownErrors(errors)).toEqual([]);
});
