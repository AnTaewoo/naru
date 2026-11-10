// 행진 예상 위치 상태 (T7.16) — ClosureProvider reducer: 고른 사건의 키프레임·재생 시각. 기록 march_be5f89a4ebf3
import { describe, expect, it } from "vitest";
import { recorded } from "../test/recorded";
import type { MarchResponse } from "../types/contracts";
import { closureReducer, initialClosureState } from "./ClosureProvider";

const body = recorded("march_be5f89a4ebf3").body as MarchResponse;

describe("행진 예상 위치 상태 (T7.16)", () => {
  it("고른 사건의 응답만 받고, 다른 사건을 열거나 닫으면 재생을 멈춘다", () => {
    let s = closureReducer(initialClosureState(), { type: "select", id: "be5f89a4ebf3" });
    s = closureReducer(s, { type: "receiveMarch", id: "2e930ec6deeb", body: null }); // 다른 사건 응답
    expect(s.march).toBeNull();
    s = closureReducer(s, { type: "receiveMarch", id: "be5f89a4ebf3", body });
    expect(s.march?.body?.keyframes).toHaveLength(241);
    const start = Date.parse("2026-11-07T12:00:00+09:00");
    s = closureReducer(s, { type: "play", ms: start });
    expect(s.playMs).toBe(start);
    expect(closureReducer(s, { type: "play", ms: start })).toBe(s);
    const other = closureReducer(s, { type: "select", id: "2e930ec6deeb" });
    expect(other.playMs).toBeNull();
    expect(other.march?.id).toBe("be5f89a4ebf3"); // 아직 그 사건 것 — 지도·카드는 id 가 같을 때만 쓴다
    const closed = closureReducer(s, { type: "select", id: null });
    expect(closed.march).toBeNull();
    expect(closed.playMs).toBeNull();
  });
});
