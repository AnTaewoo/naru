import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// 단위·렌더 테스트만 (CONVENTIONS §5.7). e2e 는 playwright.config.ts
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
    css: { modules: { classNameStrategy: "non-scoped" } },
  },
});
