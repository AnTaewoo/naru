import type { NextConfig } from "next";

/** BE(Flask) 오리진. 서버 전용 — 브라우저는 같은 오리진 `/api/*` 만 안다 (CONVENTIONS §5.2). */
export const API_ORIGIN = process.env.NARU_API_ORIGIN ?? "http://localhost:5000";

/**
 * `/api/:path*` → Flask. `/api/internal/*` 는 AI 워커 전용이라 프록시하지 않는다 (INTERFACE §1.1).
 * path-to-regexp 의 부정 전방탐색으로 internal 을 뺀다. 순수 함수라 vitest 로 검사한다.
 */
export function apiRewrites(origin: string = API_ORIGIN) {
  return [
    {
      source: "/api/:path((?!internal(?:/|$)).*)",
      destination: `${origin}/:path`,
    },
  ];
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: "standalone", // 홈서버 배포용 (static export 는 rewrites 가 안 된다)
  rewrites: async () => apiRewrites(),
};

export default nextConfig;
