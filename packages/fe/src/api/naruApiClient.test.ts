// recorded 응답(data/recorded/naru_api, scripts/record_naru_api.py 가 실제 Flask 에서 받은 것)으로
// 클라이언트의 URL·파싱을 검사한다. fetch 는 가로채지 않는다 (CONVENTIONS §5.7).
import { readdirSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { RECORDED_DIR, recorded } from "../test/recorded";
import type { FeatureCollection, RouteResponse } from "../types/contracts";
import {
  closuresUrl,
  NaruApiError,
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
});
