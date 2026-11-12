// 행진 예상 위치 (T7.16) — 기록 응답 march_be5f89a4ebf3(11/7 r01 동화면세점 고리, 12:00~16:00, 키프레임 241)로
// 보간·소스·색을 검사한다. 기대값은 기록을 열어 확인한 값(첫 키프레임 중심 = 출발점, 13:00 반경 235.4 m)
import { describe, expect, it } from "vitest";
import { recorded } from "../../test/recorded";
import type { MarchResponse } from "../../types/contracts";
import { frameAt, marchCircle, marchHeatPoints, marchLayers } from "./marchLayer";

const body = recorded("march_be5f89a4ebf3").body as MarchResponse;
const T = (hhmmss: string) => Date.parse(`2026-11-07T${hhmmss}+09:00`);
const kf = (i: number) => {
  const f = body.keyframes[i];
  if (!f) throw new Error(`키프레임 없음: ${i}`);
  return f;
};

describe("marchLayer (T7.16)", () => {
  it("12:00 — 머리가 출발점: 점 21개가 한곳, 반경 0, 세종대로사거리 P 1.0·종로구청입구 0.2", () => {
    const frame = frameAt(body, T("12:00:00"));
    expect(frame).not.toBeNull();
    expect(frame?.center).toEqual(kf(0).center);
    expect(frame?.radiusM).toBe(0);
    expect(frame?.points).toHaveLength(21);
    expect(frame?.p["06-0000036391"]).toBe(1.0);
    expect(frame?.p["06-0000002104"]).toBe(0.2);
    // 반경 0 이어도 원은 최소 250 m 로 그린다 (태우 11/11 — 슬라이더 시각의 군집이 크게) + 글로우용 중심 점
    const circle = marchCircle(frame);
    expect(circle.features.map((f) => f.geometry.type)).toEqual(["Polygon", "Point"]);
    expect(circle.features[0]?.properties.radius_m).toBe(250);
  });

  it("13:00:30 — 13:00·13:01 키프레임 사이 보간(중심·반경·P 선형, 점은 가까운 13:01)", () => {
    const a = kf(60);
    const b = kf(61);
    expect(a.t).toBe("2026-11-07T13:00:00+09:00");
    const frame = frameAt(body, T("13:00:30"));
    expect(frame).not.toBeNull();
    const mid = (x: number, y: number) => (x + y) / 2;
    expect(frame?.center[0]).toBeCloseTo(mid(Number(a.center[0]), Number(b.center[0])), 9);
    expect(frame?.radiusM).toBeCloseTo(mid(a.radius_m, b.radius_m), 9);
    expect(a.radius_m).toBe(235.4); // 속도 폭 ±20% (ADR-015 표, 11/10)
    const id = "06-0000002104";
    expect(frame?.p[id]).toBeCloseTo(mid(a.crosswalks[id] ?? 0, b.crosswalks[id] ?? 0), 9);
    expect(frame?.points).toHaveLength(b.samples.reduce((n, s) => n + s.length, 0));
    const circle = marchCircle(frame);
    const poly = circle.features[0]?.geometry;
    expect(poly?.type === "Polygon" ? poly.coordinates[0] : []).toHaveLength(65);
    // 퍼짐 237.4 m < 최소 250 m → 원은 250 m (CIRCLE_MIN_M)
    expect(circle.features[0]?.properties.radius_m).toBe(Math.max(frame?.radiusM ?? 0, 250));
    expect(circle.features[0]?.properties.radius_m).toBe(250);
  });

  it("창 밖은 null → 소스는 빈 컬렉션; 끝 시각은 마지막 키프레임", () => {
    expect(frameAt(body, T("11:59:59"))).toBeNull();
    expect(frameAt(body, T("16:00:01"))).toBeNull();
    expect(marchHeatPoints(null).features).toHaveLength(0);
    expect(marchCircle(null).features).toHaveLength(0);
    const end = frameAt(body, T("16:00:00"));
    expect(end?.center).toEqual(kf(240).center);
  });

  it("레이어는 군집뿐 — heatmap·글로우·채움·테두리, 횡단보도 P 점 없음 (태우 11/12: 횡단보도 통제는 사건 전 구역)", () => {
    expect(marchLayers().map((l) => l.type)).toEqual(["heatmap", "circle", "fill", "line"]);
  });
});
