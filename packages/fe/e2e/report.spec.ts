// T7.15 통제 제보 — iPhone 13. 위치는 Playwright 위치 권한(실데이터 좌표): 교보빌딩 = recorded route_0745 출발
// (카카오 24020019), 서울 밖 = 경기 성남(locate.spec 과 같은 점). 실제 앱(임시 스택 naru_test 에 BE 0006):
// 지도 "제보" → 가장 가까운 횡단보도(OA-23081 '교보생명' 71 m) 핀·카드 → 막혔어요 → 201 → 같은 기기·같은
// 횡단보도를 바로 다시 → 429 "조금 뒤에". 좌표는 POST 본문으로만 간다(주소에 없다)
import { devices, expect, test, type BrowserContext } from "@playwright/test";
import { recorded } from "../src/test/recorded";
import { consoleErrors, denyGeolocation, ownErrors } from "./helpers";

const iphone = devices["iPhone 13"];
test.use({
  viewport: iphone.viewport,
  deviceScaleFactor: iphone.deviceScaleFactor,
  isMobile: iphone.isMobile,
  hasTouch: iphone.hasTouch,
  userAgent: iphone.userAgent,
});

const q = recorded("route_0745").query ?? {};
function geo(latLng: string | undefined) {
  const [latitude = Number.NaN, longitude = Number.NaN] = (latLng ?? "").split(",").map(Number);
  return { latitude, longitude };
}
const KYOBO = { ...geo(q["from"]), accuracy: 14 };
const SEONGNAM = { ...geo("37.3947,127.1112"), accuracy: 14 };

async function locatedAt(context: BrowserContext, where: typeof KYOBO) {
  await context.grantPermissions(["geolocation"]);
  await context.setGeolocation(where);
}

test("제보 → 교보생명(71 m) 핀·카드 → 막혔어요 201 → 같은 횡단보도 바로 다시는 429 '조금 뒤에'", async ({
  page,
  context,
}) => {
  const errors = consoleErrors(page);
  await locatedAt(context, KYOBO);
  await page.goto("/");
  const nearest = page.waitForRequest((r) => r.url().includes("/api/crosswalks/nearest"));
  await page.getByRole("button", { name: "통제 제보" }).click();
  const asked = await nearest;
  expect(new URL(asked.url()).search).toBe(""); // 좌표는 주소가 아니라 본문
  expect(asked.method()).toBe("POST");
  expect(asked.postDataJSON()).toEqual({ lat: KYOBO.latitude, lng: KYOBO.longitude });
  const card = page.getByRole("article", { name: "통제 제보" });
  await expect(card).toContainText("이 횡단보도가 맞나요?");
  await expect(card).toContainText("교보생명");
  await expect(card).toContainText("여기서 71 m · 위치 정확도 ±14 m");
  await expect(page.getByRole("img", { name: "교보생명 위치" })).toBeVisible();
  const sent = page.waitForResponse((r) => r.url().endsWith("/api/reports"));
  await card.getByRole("button", { name: "막혔어요" }).click();
  const res = await sent;
  expect(res.status()).toBe(201);
  const body = res.request().postDataJSON() as Record<string, unknown>;
  expect(body).toMatchObject({ crosswalk_id: "06-0000051345", state: "blocked", source: "user" });
  expect(body).not.toHaveProperty("lat");
  await expect(card.getByRole("status")).toContainText("막혔다고 제보했어요");
  // 같은 브라우저(기기 토큰 localStorage)가 같은 횡단보도를 바로 다시 → 429
  await card.getByRole("button", { name: "제보 닫기" }).click();
  await expect(page.getByRole("img", { name: "교보생명 위치" })).toHaveCount(0);
  await page.getByRole("button", { name: "통제 제보" }).click();
  const again = page.waitForResponse((r) => r.url().endsWith("/api/reports"));
  await card.getByRole("button", { name: "열렸어요" }).click();
  expect((await again).status()).toBe(429);
  await expect(card.getByRole("alert")).toContainText("조금 뒤에 다시");
  // 429 는 이 테스트가 기대한 응답 — 그 밖의 오류는 없어야 한다
  expect(ownErrors(errors).filter((e) => !/status of 429/.test(e))).toEqual([]);
});

test("?mode=field 면 '현장 검증' 배지·출처 field", async ({ page, context }) => {
  await locatedAt(context, KYOBO);
  await page.goto("/?mode=field");
  await page.getByRole("button", { name: "통제 제보" }).click();
  const card = page.getByRole("article", { name: "통제 제보" });
  await expect(card).toContainText("현장 검증");
  const sent = page.waitForResponse((r) => r.url().endsWith("/api/reports"));
  await card.getByRole("button", { name: "열렸어요" }).click();
  const res = await sent;
  expect(res.status()).toBe(201);
  expect(res.request().postDataJSON()).toMatchObject({ source: "field", state: "open" });
  await expect(card.getByRole("status")).toContainText("열렸다고 제보했어요");
});

test("서울 밖(성남)은 '가까운 횡단보도를 찾지 못했어요', 위치 권한이 꺼져 있으면 그렇게 말한다", async ({
  page,
  context,
  browser,
}) => {
  await locatedAt(context, SEONGNAM);
  await page.goto("/");
  await page.getByRole("button", { name: "통제 제보" }).click();
  const card = page.getByRole("article", { name: "통제 제보" });
  await expect(card.getByRole("alert")).toContainText("가까운 횡단보도를 찾지 못했어요");
  await card.getByRole("button", { name: "제보 닫기" }).click();
  await context.clearPermissions();
  const cdp = await denyGeolocation(browser, page);
  await page.getByRole("button", { name: "통제 제보" }).click();
  await expect(card.getByRole("alert")).toContainText("위치 권한이 꺼져 있어");
  await cdp.detach();
});
