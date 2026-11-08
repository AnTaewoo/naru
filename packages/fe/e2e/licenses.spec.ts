// 오픈소스·데이터 고지 (태우 2026-11-08): 하단 시트 맨 아래 줄(모바일)·푸터(데스크톱)에서 /licenses 로,
// maplibre-gl BSD-3-Clause 전문. 지도 출처 칸은 OSM 한 줄만 (T5.12 — OSMF 타일 정책 §2 "Do not hide
// attribution beneath UI, behind toggles, or off-screen", 2026-11-08 원문 확인 → 숨기기·접기는 안 된다)
import { expect, test } from "@playwright/test";
import { consoleErrors, ownErrors } from "./helpers";

const LEGAL = "오픈소스·데이터 고지";

test("고지 — 지도 출처 칸은 'OSM' 한 줄, 시트를 펼치면 맨 아래 '오픈소스·데이터 고지' → /licenses", async ({
  page,
}) => {
  const errors = consoleErrors(page);
  await page.goto("/?t=2026-03-15T07:45:00+09:00");
  // 출처 칸: 타일 출처 하나만, 펼친 채(접기 버튼 없음)
  const attrib = page.locator(".maplibregl-ctrl-attrib-inner");
  await expect(attrib).toHaveText("© OpenStreetMap contributors");
  await expect(page.getByRole("link", { name: "오픈소스 고지" })).toHaveCount(0);
  await expect(page.locator(".maplibregl-ctrl-attrib-button")).toBeHidden();
  // 홈 시트는 절반으로 시작 → 고지 줄이 보인다. 접으면 없고, 다시 펴면 있다
  const legal = page.getByRole("main").getByRole("link", { name: LEGAL });
  await expect(legal).toBeVisible();
  const grip = page.getByRole("button", { name: "시트 높이" });
  await grip.click();
  await expect(legal).toHaveCount(0);
  await grip.click();
  await legal.click();
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
  // 모바일(≤640px)은 푸터를 숨긴다(T5.6) — 넓은 화면은 푸터 링크만, 시트의 고지 줄은 숨김
  test.use({ viewport: { width: 1024, height: 800 } });
  test("고지 — 푸터 링크, 시트 고지 줄은 안 보임, 출처 칸은 OSM 한 줄", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator(".maplibregl-ctrl-attrib-inner")).toHaveText(
      "© OpenStreetMap contributors",
    );
    await expect(page.getByRole("main").getByRole("link", { name: LEGAL })).toBeHidden();
    await page.getByRole("contentinfo").getByRole("link", { name: LEGAL }).click();
    await expect(page).toHaveURL(/\/licenses$/);
  });
});
