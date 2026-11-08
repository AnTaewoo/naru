// recorded 응답(data/recorded/naru_api, scripts/record_naru_api.py 가 실제 Flask 에서 받은 것)으로
// 클라이언트의 URL·파싱을 검사한다. fetch 는 가로채지 않는다 (CONVENTIONS §5.7).
import { readdirSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { RECORDED_DIR, recorded } from "../test/recorded";
import type { ErrorBody, FeatureCollection, RouteResponse } from "../types/contracts";
import {
  closuresUrl,
  eventsUrl,
  geocodeReverseUrl,
  geocodeSearchUrl,
  NaruApiError,
  parseClosureEvents,
  parseFeatureCollection,
  parseGeocodeReverse,
  parseGeocodeSearch,
  parseRouteResponse,
  placeLngLat,
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
    // v0.12 data_as_of 필수 — 기록: 경찰청 11/6 18:00 공지, 마라톤 3/12 16:07 시각표
    expect(body.data_as_of.smpa).toBe("2026-11-06T18:00:00+09:00");
    expect(() => parseClosureEvents({ events: body.events, coverage: body.coverage })).toThrow(
      NaruApiError,
    );
  });

  it("지오코딩 (INTERFACE §7, T5.8) — URL, recorded 검색·주소 응답 파싱, 오류 본문", () => {
    const base = "http://naru.test";
    const search = new URL(
      geocodeSearchUrl("/api", { q: "교보빌딩", near: "37.5675,126.9775" }),
      base,
    );
    expect(search.pathname).toBe("/api/geocode/search");
    expect(search.searchParams.get("q")).toBe("교보빌딩");
    expect(search.searchParams.get("near")).toBe("37.5675,126.9775");
    expect(new URL(geocodeSearchUrl("/api", { q: "시청" }), base).searchParams.has("near")).toBe(
      false,
    );
    const rev = new URL(
      geocodeReverseUrl("/api", { lat: 37.5709686446227, lng: 126.9779039768265 }),
      base,
    );
    expect(rev.pathname).toBe("/api/geocode/reverse");
    expect(rev.searchParams.get("lat")).toBe("37.5709686446227");
    expect(rev.searchParams.get("lng")).toBe("126.9779039768265");
    // recorded naru_api/geocode_*.json — 카카오 기록을 재생한 실제 Flask 응답 (MANIFEST 를 열어 확인)
    const rec = recorded("geocode_search_kyobo");
    expect(rec.query).toEqual({ q: "교보빌딩", near: "37.5675,126.9775" });
    const found = parseGeocodeSearch(rec.body);
    expect(found.places).toHaveLength(10);
    const first = found.places[0];
    if (!first) throw new Error("기록에 장소가 없다");
    expect([first.name, first.address]).toEqual(["광화문교보빌딩", "서울 종로구 종로 1"]);
    expect(placeLngLat(first)).toEqual([126.9779039768265, 37.5709686446227]);
    expect(parseGeocodeReverse(recorded("geocode_reverse_kyobo").body).label).toBe("종로구 종로 1");
    const noRoad = parseGeocodeReverse(recorded("geocode_reverse_sejong_to").body);
    expect([noRoad.label, noRoad.road_address]).toEqual(["중구 남대문로2가 9-9", null]);
    expect(() => parseGeocodeSearch(recorded("geocode_reverse_kyobo").body)).toThrow(NaruApiError);
    expect(() => parseGeocodeReverse(rec.body)).toThrow(NaruApiError);
    const err = recorded("error_geocode_unavailable");
    expect(err.status).toBe(503);
    expect((err.body as ErrorBody).error.code).toBe("geocode_unavailable");
  });
});
