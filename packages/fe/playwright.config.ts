import { defineConfig } from "@playwright/test";

// e2e: `make dev` 로 Flask(:5000) + next dev(:3000) 를 띄운 뒤 `pnpm e2e` (CONVENTIONS §5.7-3). T5.3 에서 채운다
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  use: {
    baseURL: process.env.NARU_FE_ORIGIN ?? "http://localhost:3000",
    trace: "retain-on-failure",
  },
  reporter: [["list"]],
});
