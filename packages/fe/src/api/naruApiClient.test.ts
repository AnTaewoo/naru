// recorded 응답(data/recorded/naru_api, scripts/record_naru_api.py 가 실제 Flask 에서 받은 것)으로
// 클라이언트의 URL·파싱을 검사한다. fetch 는 가로채지 않는다 (CONVENTIONS §5.7).
import { readdirSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { RECORDED_DIR, recorded } from "../test/recorded";
import type { FeatureCollection, RouteResponse } from "../types/contracts";
import {
  closuresUrl,
  eventsUrl,
  NaruApiError,
  parseClosureEvents,
  parseFeatureCollection,
  parseRouteResponse,
  routeUrl,
} from "./naruApiClient";

describe("naruApiClient", () => {
  it("기록 폴더가 있다 (없으면 make record-naru-api 먼저)", () => {
    const names = readdirSync(RECORDED_DIR);
    expect(names).toContain("route_0745.json");
    expect(names).toContain("closures_0745.json");
  });

  it("URL 은 INTERFACE §2·§3 쿼리 이름을 쓴다", () => {
    const url = routeUrl("/api", {
      from: "37.5709686446227,126.9779039768265",
      to: "37.5650416322942,126.976542945622",
      departAt: "2026-03-15T07:45:00+09:00",
    });
    expect(url.startsWith("/api/route?")).toBe(true);
    const q = new URL(url, "http://naru.test").searchParams;
    expect(q.get("from")).toBe("37.5709686446227,126.9779039768265");
    expect(q.get("depart_at")).toBe("2026-03-15T07:45:00+09:00");
    expect(q.get("mode")).toBe("walk");
    const c = new URL(
      closuresUrl("/api", {
        bbox: "126.965,37.555,126.990,37.580",
        at: "2026-03-15T07:45:00+09:00",
      }),
      "http://naru.test",
    );
    expect(c.pathname).toBe("/api/closures");
    expect(c.searchParams.get("bbox")).toBe("126.965,37.555,126.990,37.580");
  });

  it("recorded /route 응답이 RouteResponse 로 읽힌다 (통제 중 07:45 → 지하보도 레그)", () => {
    const rec = recorded("route_0745");
    expect(rec.status).toBe(200);
    const body: RouteResponse = parseRouteResponse(rec.body);
    expect(body.route.type).toBe("LineString");
    expect(body.legs.map((l) => l.kind)).toContain("underpass");
    const underpass = body.legs.find((l) => l.kind === "underpass");
    expect(underpass?.coord_range).toEqual([3, 8]); // INTERFACE v0.7, ADR-009
    expect(body.avoided.length).toBeGreaterThan(0);
    expect(body.baseline.distance_m).toBeLessThan(body.distance_m);
    expect(body.computed_at.endsWith("+09:00")).toBe(true);
    const free = parseRouteResponse(recorded("route_1330").body);
    expect(free.avoided).toEqual([]);
    expect(free.distance_m).toBe(free.baseline.distance_m);
  });

  it("recorded /closures 응답이 FeatureCollection 으로 읽힌다", () => {
    const fc: FeatureCollection = parseFeatureCollection(recorded("closures_0745").body);
    expect(fc.features.length).toBeGreaterThan(0);
    const first = fc.features[0];
    expect(first?.geometry.type).toBe("Point");
    expect(first?.properties.status).toBe("confirmed");
    expect(parseFeatureCollection(recorded("closures_1330").body).features).toEqual([]);
  });

  it("오류 응답은 §6 ErrorBody 모양이고, 계약과 다른 본문은 파서가 거부한다", () => {
    const err = recorded("error_invalid_query");
    expect(err.status).toBe(400);
    const body = err.body as { error: { code: string; field: string | null } };
    expect(body.error.code).toBe("invalid_query");
    expect(body.error.field).toBe("depart_at");
    expect(() => parseRouteResponse(err.body)).toThrow(NaruApiError);
    expect(() => parseFeatureCollection({ type: "Feature" })).toThrow(NaruApiError);
  });

  it("통제 사건 (INTERFACE §3.1, T5.4) — URL 은 bbox 선택, recorded 응답을 그대로 파싱", () => {
    expect(eventsUrl("/api")).toBe("/api/closures/events");
    const scoped = new URL(
      eventsUrl("/api", { bbox: "126.965,37.555,126.990,37.580" }),
      "http://naru.test",
    );
    expect(scoped.pathname).toBe("/api/closures/events");
    expect(scoped.searchParams.get("bbox")).toBe("126.965,37.555,126.990,37.580");
    const rec = recorded("closure_events");
    expect(rec.path).toBe("/closures/events");
    const body = parseClosureEvents(rec.body);
    // 기록 당시 개발 DB: 11/7 집회 2 + 3/15 마라톤 5, 시작 늦은 순 (closure_events.json 을 열어 확인)
    expect(body.events).toHaveLength(7);
    expect(body.events[0]?.window.start).toBe("2026-11-07T15:00:00+09:00");
    expect(body.events[0]?.crosswalks).toBe(31);
    expect(body.events.at(-1)?.reason).toBe("marathon 출발지 광화문 광장 (미국대사관 앞 세종대로)");
    // v0.10 coverage — 보행망 노드 bbox (T5.7 재기록). 없으면 계약 위반
    expect(body.coverage).toHaveLength(4);
    expect(() => parseClosureEvents(recorded("closures_0745").body)).toThrow(NaruApiError);
    expect(() => parseClosureEvents({ events: body.events })).toThrow(NaruApiError);
  });
});
