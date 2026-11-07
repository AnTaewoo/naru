// next.config.ts 의 rewrites 는 순수 함수 — /api/* 는 Flask 로, /api/internal/* 는 프록시하지 않는다
import { describe, expect, it } from "vitest";
import { apiRewrites } from "../next.config";

// Next 가 쓰는 path-to-regexp 와 같은 꼴로 source 를 정규식으로 바꿔 본다 (`:path(<regex>)` 하나뿐)
function sourceMatches(source: string, pathname: string): boolean {
  const m = /^\/api\/:path\((.*)\)$/.exec(source);
  if (!m) throw new Error(`예상 밖 source: ${source}`);
  return new RegExp(`^/api/(${m[1]})$`).test(pathname);
}

describe("apiRewrites", () => {
  it("/api/:path* → NARU_API_ORIGIN/:path", () => {
    const [rule] = apiRewrites("http://flask.test:5000");
    expect(rule?.destination).toBe("http://flask.test:5000/:path");
    expect(sourceMatches(rule?.source ?? "", "/api/route")).toBe(true);
    expect(sourceMatches(rule?.source ?? "", "/api/closures")).toBe(true);
  });

  it("/api/internal/* 는 제외한다 (AI 워커 전용, INTERFACE §1.1)", () => {
    const [rule] = apiRewrites("http://flask.test:5000");
    expect(sourceMatches(rule?.source ?? "", "/api/internal/candidates")).toBe(false);
    expect(sourceMatches(rule?.source ?? "", "/api/internal")).toBe(false);
    expect(sourceMatches(rule?.source ?? "", "/api/internals")).toBe(true); // 접두사가 아니라 경로 단위
  });

  it("기본 오리진은 127.0.0.1:5000 (localhost 는 Node 18 에서 ::1)", () => {
    const [rule] = apiRewrites();
    expect(rule?.destination.startsWith("http://127.0.0.1:5000/")).toBe(true);
  });
});
