// T7.7 PWA 바탕 — 매니페스트·아이콘·서비스워커 등록·알림 권한 칸. 실제 앱(임시 스택). Chromium 은 127.0.0.1 을
// 안전한 출처로 봐서 서비스워커가 등록된다. 권한은 Playwright 가 준다(묻는 창은 헤드리스에서 안 뜬다)
import { devices, expect, test } from "@playwright/test";
import { consoleErrors, expandSheet, ownErrors } from "./helpers";

const iphone = devices["iPhone 13"];
test.use({
  viewport: iphone.viewport,
  deviceScaleFactor: iphone.deviceScaleFactor,
  isMobile: iphone.isMobile,
  hasTouch: iphone.hasTouch,
  userAgent: iphone.userAgent,
});

test("매니페스트·아이콘·서비스워커가 제공되고, 페이지가 /sw.js 를 scope / 로 등록한다", async ({
  page,
  request,
}) => {
  const manifest = await request.get("/manifest.webmanifest");
  expect(manifest.status()).toBe(200);
  const body = (await manifest.json()) as {
    name: string;
    short_name: string;
    display: string;
    start_url: string;
    icons: { src: string; sizes: string; purpose?: string }[];
  };
  expect(body.short_name).toBe("나루");
  expect(body.display).toBe("standalone");
  expect(body.icons.map((i) => i.sizes)).toEqual(["192x192", "512x512", "512x512"]);
  for (const icon of body.icons) expect((await request.get(icon.src)).status()).toBe(200);
  const sw = await request.get("/sw.js");
  expect(sw.status()).toBe(200);
  expect(sw.headers()["content-type"]).toContain("javascript");
  const errors = consoleErrors(page);
  await page.goto("/");
  await expect(page.locator('link[rel="manifest"]')).toHaveAttribute(
    "href",
    /manifest\.webmanifest/,
  );
  const scope = await page.evaluate(async () => (await navigator.serviceWorker.ready).scope);
  expect(scope).toBe(`${new URL(page.url()).origin}/`);
  expect(ownErrors(errors)).toEqual([]);
});

test("알림 칸 — 권한이 없으면 '통제 알림 받기' 버튼 (iPhone UA 라도 홈 화면이면 보통)", async ({
  page,
}) => {
  // iPhone 13 UA 지만 Chromium 이라 Notification 이 있다 — 브라우저 탭(standalone 아님)이면 홈 화면 안내
  await page.goto("/?t=2026-11-08T12:00:00%2B09:00");
  await expandSheet(page, "서울 통제");
  const box = page.getByRole("region", { name: "통제 알림" });
  await expect(box).toContainText("홈 화면에 추가");
});

test("권한이 허용돼 있으면 '알림이 허용됐어요' — 데스크톱 UA", async ({ browser }) => {
  const context = await browser.newContext({
    ...devices["Desktop Chrome"],
    permissions: ["notifications"],
    viewport: { width: 430, height: 900 },
  });
  const page = await context.newPage();
  await page.goto("/?t=2026-11-08T12:00:00%2B09:00");
  await expandSheet(page, "서울 통제");
  const box = page.getByRole("region", { name: "통제 알림" });
  await expect(box).toContainText("알림이 허용됐어요"); // 구독은 아직 — 버튼은 남는다 (T7.10)
  await expect(box.getByRole("button", { name: "통제 알림 받기" })).toBeVisible();
  await context.close();
});

test("권한이 아직이면 버튼 — 데스크톱 UA, 누르면 권한을 묻는다(헤드리스는 거부로 끝난다)", async ({
  browser,
}) => {
  const context = await browser.newContext({
    ...devices["Desktop Chrome"],
    viewport: { width: 430, height: 900 },
  });
  const page = await context.newPage();
  await page.goto("/?t=2026-11-08T12:00:00%2B09:00");
  await expandSheet(page, "서울 통제");
  const box = page.getByRole("region", { name: "통제 알림" });
  await expect(box.getByRole("button", { name: "통제 알림 받기" })).toBeVisible();
  await context.close();
});
