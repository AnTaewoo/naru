// `make dev` 뒤 `pnpm e2e`. 홈이 열리고 rewrites 로 /api/closures 가 Flask 까지 간다 (T5.3 에서 확장)
import { expect, test } from "@playwright/test";

test("홈이 열린다", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "나루" })).toBeVisible();
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
