// 실제 브라우저 푸시 구독 기록 (T7.8) — scripts/record_push_subscription.py 가 부른다. 인자: VAPID 공개키, 앱 주소,
// 프로필 폴더. 시크릿 컨텍스트는 Push API 가 없어(crbug 401439) 영속 프로필로 연다. 출력: 구독 JSON 한 줄
import { createRequire } from "node:module";
const require = createRequire(process.cwd() + "/package.json");
const { chromium } = require("@playwright/test");
const [pub, origin, profile, mode] = process.argv.slice(2); // mode "gone": 구독하고 바로 해지 — 발송하면 410
const ctx = await chromium.launchPersistentContext(profile, {
  executablePath: process.env.NARU_CHROME_PATH || undefined,
  headless: true,
  permissions: ["notifications"],
  args: ["--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--ignore-gpu-blocklist"],
});
const page = await ctx.newPage();
await page.goto(`${origin}/`);
const sub = await page.evaluate(async ([key, mode]) => {
  const reg = await navigator.serviceWorker.ready;
  const pad = "=".repeat((4 - (key.length % 4)) % 4);
  const raw = atob(key.replace(/-/g, "+").replace(/_/g, "/") + pad);
  const bytes = Uint8Array.from(raw, (c) => c.charCodeAt(0));
  const s = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: bytes });
  const json = s.toJSON();
  const gone = mode === "gone" ? await s.unsubscribe() : false;
  return { subscription: json, userAgent: navigator.userAgent, gone };
}, [pub, mode]).then((r) => r);
console.log(JSON.stringify(sub));
await ctx.close();
