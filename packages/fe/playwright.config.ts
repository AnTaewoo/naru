import { defineConfig } from "@playwright/test";

// e2e: `make dev`(Flask :5000 + next :3000) 를 띄운 뒤 `pnpm e2e` (CONVENTIONS §5.7-3).
// 브라우저는 Playwright 내려받기 대신 설치된 Chrome 을 쓸 수 있다: NARU_CHROME_PATH=/usr/local/bin/google-chrome
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  outputDir: "test-results",
  use: {
    baseURL: process.env.NARU_FE_ORIGIN ?? "http://localhost:3000",
    trace: "retain-on-failure",
    viewport: { width: 430, height: 900 }, // 목업(폰) 비율
    launchOptions: {
      executablePath: process.env.NARU_CHROME_PATH || undefined,
      // 헤드리스에서 maplibre(WebGL2) — GPU 없이 SwiftShader 로 그린다
      args: ["--enable-unsafe-swiftshader", "--use-angle=swiftshader", "--ignore-gpu-blocklist"],
    },
  },
  reporter: [["list"]],
});
