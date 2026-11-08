// `make dev` 뒤 `pnpm e2e`. 실제 Flask(:5000, 개발 DB) + Next(:3000) 끝에서 끝으로 (CONVENTIONS §5.7-3)
import { expect, test } from "@playwright/test";

test("홈이 열린다", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "나루" })).toBeAttached();
  await expect(page.getByText("오늘 통제", { exact: true })).toBeVisible();
});

test("/api/closures 가 Flask 로 프록시된다", async ({ request }) => {
  const res = await request.get(
    "/api/closures?bbox=126.965,37.555,126.990,37.580&at=2026-03-15T07:45:00%2B09:00",
  );
  expect(res.status()).toBe(200);
  const body = (await res.json()) as { type: string };
  expect(body.type).toBe("FeatureCollection");
});

test("/api/internal/* 는 프록시하지 않는다", async ({ request }) => {
  const res = await request.post("/api/internal/candidates", { data: {} });
  expect(res.status()).toBe(404);
});

test("통제 중 시각(?t=…+09:00) — 지도 캔버스·워커·통제 시트", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.on("pageerror", (e) => errors.push(e.message));
  const worker = page.waitForResponse((r) => r.url().includes("maplibre-gl-worker"));
  // 주소창에 치듯 + 를 그대로 — 쿼리 해석에서 공백이 되는 걸 TimeProvider 가 되돌린다
  await page.goto("/?t=2026-03-15T07:45:00+09:00");
  const workerRes = await worker;
  expect(workerRes.status()).toBe(200);
  expect(workerRes.headers()["content-type"] ?? "").toMatch(/javascript/);
  await expect(page.locator("canvas.maplibregl-canvas")).toBeVisible();
  await expect(page.getByText("07:45", { exact: true })).toBeVisible();
  await expect(page.getByText(/횡단보도 \d+곳 통제 중/)).toBeVisible();
  await expect(page.getByText("마라톤 1구간 세종대로 사거리~숭례문 오거리")).toBeVisible();
  await expect(page.getByText("23분 뒤 해제")).toBeVisible(); // 1구간 08:08 해제 — 배지가 잘리지 않는다
  await page.waitForTimeout(2500); // 타일·심볼이 그려질 시간 (스크린샷용)
  await page.screenshot({ path: "test-results/home-0745.png" });
  // 콘솔 오류 없음 — 워커·WebGL·하이드레이션 불일치 포함. 배경 타일 서버 오류(외부)만 뺀다
  expect(errors.filter((e) => !/tile\.openstreetmap|api\.vworld/i.test(e))).toEqual([]);
});
