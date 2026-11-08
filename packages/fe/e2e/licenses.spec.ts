// 오픈소스·데이터 고지 (태우 2026-11-08): 지도 출처 칸과 푸터에서 /licenses 로, maplibre-gl BSD-3-Clause 전문
import { expect, test } from "@playwright/test";
import { consoleErrors, ownErrors } from "./helpers";

test("고지 — 지도 출처 칸의 '오픈소스 고지' → /licenses: 타일·데이터·maplibre-gl 전문", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto("/?t=2026-03-15T07:45:00+09:00");
  await page.getByRole("link", { name: "오픈소스 고지" }).click();
  await expect(page).toHaveURL(/\/licenses$/);
  await expect(page.getByRole("heading", { name: "오픈소스·데이터 고지" })).toBeVisible();
  await expect(page.getByRole("link", { name: "© OpenStreetMap contributors" })).toBeVisible();
  await expect(page.getByText("OA-21208", { exact: false })).toBeVisible();
  const maplibre = page.getByRole("article", { name: /maplibre-gl/ });
  await expect(maplibre).toContainText("BSD-3-Clause");
  await expect(maplibre).toContainText("Copyright (c) 2023, MapLibre contributors");
  await expect(maplibre).toContainText("Copyright (c) 2020, Mapbox");
  await expect(page.getByRole("article", { name: /react-dom/ })).toContainText("MIT");
  expect(ownErrors(errors)).toEqual([]);
});

test.describe("데스크톱 폭", () => {
  // 모바일(≤640px)은 푸터를 숨긴다(T5.6) — 푸터 링크는 넓은 화면에서 본다
  test.use({ viewport: { width: 1024, height: 800 } });
  test("고지 — 푸터 링크", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("contentinfo").getByRole("link", { name: "오픈소스·데이터 고지" }).click();
    await expect(page).toHaveURL(/\/licenses$/);
  });
});
