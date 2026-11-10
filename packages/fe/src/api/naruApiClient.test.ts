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
  readEvents,
  eventsInit,
  routeUrl,
  marchOrNull,
  marchUrl,
  nearestUrl,
  parseMarch,
  parseNearestCrosswalk,
  parseRecentReports,
  parseReportResponse,
  postInit,
  readJson,
  recentReportsUrl,
  reportsUrl,
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
    expect(q.get("avoid")).toBeNull(); // 피할 사건이 없으면 안 보낸다
    // v0.14 avoid (T7.6) — 사건 id 쉼표. 마라톤 1구간 adaea2f4cc02 (사건 v2 기록 closure_events_live_0315_0745)
    const avoid = routeUrl("/api", {
      from: "37.5709686446227,126.9779039768265",
      to: "37.5650416322942,126.976542945622",
      departAt: "2026-03-15T13:30:00+09:00",
      avoid: ["adaea2f4cc02"],
    });
    expect(new URL(avoid, "http://naru.test").searchParams.get("avoid")).toBe("adaea2f4cc02");
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

  it("통제 사건 (INTERFACE §3.1) — URL 은 bbox 선택, recorded 응답을 그대로 파싱", () => {
    expect(eventsUrl("/api")).toBe("/api/closures/events");
    const scoped = new URL(
      eventsUrl("/api", { bbox: "126.965,37.555,126.990,37.580" }),
      "http://naru.test",
    );
    expect(scoped.pathname).toBe("/api/closures/events");
    expect(scoped.searchParams.get("bbox")).toBe("126.965,37.555,126.990,37.580");
    const rec = recorded("closure_events_live_1107_1530");
    expect(rec.path).toBe("/closures/events");
    const body = parseClosureEvents(rec.body);
    // 11/7 15:30 사건 13, 시작 늦은 순 — 처음은 경찰청 r06 16:00, 끝은 TOPIS 공지 6300 05:00 (기록을 열어 확인)
    expect(body.events).toHaveLength(13);
    expect(body.events[0]?.window.start).toBe("2026-11-07T16:00:00+09:00");
    expect(body.events.at(-1)?.source).toBe("topis");
    // v0.10 coverage — 보행망 bbox. 없으면 계약 위반
    expect(body.coverage).toHaveLength(4);
    expect(() => parseClosureEvents(recorded("closures_0745").body)).toThrow(NaruApiError);
    expect(() => parseClosureEvents({ events: body.events })).toThrow(NaruApiError);
    // v0.12 data_as_of 필수 — 경찰청 PDF 기준 작성 11/6 18:00
    expect(body.data_as_of.smpa).toBe("2026-11-06T18:00:00+09:00");
    const { events, coverage, data_as_of } = body;
    expect(() => parseClosureEvents({ events, coverage })).toThrow(NaruApiError);
    expect(() => parseClosureEvents({ events, coverage, data_as_of })).toThrow(NaruApiError); // v0.14 at
  });

  it("사건 v2 조건부 요청 (T7.4) — at 질의, If-None-Match·no-store, 304 면 그대로", () => {
    // scripts/record_live_events.py 가 실제 앱에서 받은 응답 — 보낸 질의·받은 ETag 를 같이 남겼다
    const rec = recorded("closure_events_live_1107_1530");
    expect(rec.query).toEqual({ at: "2026-11-07T15:30:00+09:00" });
    const url = new URL(eventsUrl("/api", { at: "2026-11-07T15:30:00+09:00" }), "http://naru.test");
    expect(url.pathname).toBe("/api/closures/events");
    expect(url.searchParams.get("at")).toBe("2026-11-07T15:30:00+09:00");
    const etag = rec.etag ?? null;
    expect(etag).toMatch(/^"[0-9a-f]{40}"$/); // 본문 sha1 (closure_view.render_events)
    const got = readEvents(200, etag, rec.body);
    if (!got.changed) throw new Error("200 인데 바뀐 것 없음");
    expect(got.etag).toBe(etag);
    expect(got.body.at).toBe("2026-11-07T15:30:00+09:00");
    expect(got.body.events).toHaveLength(13);
    expect(got.body.truncated).toBe(false);
    // 브라우저 캐시를 거치지 않고 If-None-Match 를 직접 단다 — 304 를 JS 가 본다
    // 시트 목록(T7.12)은 넓은 창 — from·to 를 같이 (넓은 창 기록의 질의 그대로)
    const wide = recorded("closure_events_catalog_1107_1530").query ?? {};
    const w = new URL(
      eventsUrl("/api", { at: wide["at"], from: wide["from"], to: wide["to"] }),
      "http://naru.test",
    );
    expect([w.searchParams.get("from"), w.searchParams.get("to")]).toEqual([
      "2025-11-07T15:30:00+09:00",
      "2027-11-07T15:30:00+09:00",
    ]);
    expect(eventsInit(null)).toMatchObject({ cache: "no-store", headers: {} });
    expect(eventsInit(null).headers).not.toHaveProperty("if-none-match");
    expect(eventsInit(etag).headers).toMatchObject({ "if-none-match": etag });
    expect(readEvents(304, etag, null, etag)).toEqual({ changed: false, etag });
    expect(readEvents(304, null, null, etag)).toEqual({ changed: false, etag }); // ETag 머리가 없으면 보낸 것
    // v0.14 응답 at 필수 — 그 전 기록(closure_events.json, T5.4)은 계약 위반
    expect(() => readEvents(200, null, recorded("closure_events").body)).toThrow(NaruApiError);
    const err = recorded("error_invalid_query");
    expect(() => readEvents(err.status, null, err.body)).toThrow(NaruApiError);
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

  it("통제 제보 (INTERFACE §8, T7.15) — 좌표는 POST 본문에만, recorded 응답 파싱, 429 본문", () => {
    const near = recorded("report_nearest_kyobo");
    expect(near.method).toBe("POST");
    expect(nearestUrl("/api")).toBe("/api/crosswalks/nearest"); // 주소에 좌표가 없다
    const init = postInit(near.json);
    expect(init).toMatchObject({ method: "POST", cache: "no-store" });
    expect(init.headers).toMatchObject({ "content-type": "application/json" });
    expect(JSON.parse(String(init.body))).toEqual({
      lat: 37.5709686446227,
      lng: 126.9779039768265,
    });
    expect(parseNearestCrosswalk(near.body).crosswalk?.name).toBe("교보생명");
    expect(parseNearestCrosswalk(recorded("report_nearest_none").body).crosswalk).toBeNull();
    // 다른 응답(최근 제보 집계)은 최근접 모양이 아니다
    expect(() => parseNearestCrosswalk(recorded("reports_recent").body)).toThrow(NaruApiError);
    expect(reportsUrl("/api")).toBe("/api/reports");
    const sent = recorded("report_sent");
    expect(sent.status).toBe(201);
    const saved = parseReportResponse(readJson(sent.status, sent.body));
    expect([saved.crosswalk_id, saved.state]).toEqual(["06-0000051345", "blocked"]);
    expect(saved.reported_at).toMatch(/\+09:00$/);
    const tooMany = recorded("report_too_many");
    expect(() => readJson(tooMany.status, tooMany.body)).toThrow(NaruApiError);
    try {
      readJson(tooMany.status, tooMany.body);
    } catch (e) {
      expect(e instanceof NaruApiError && e.body?.error.code).toBe("too_many_reports");
    }
    const recent = recorded("reports_recent");
    const q = new URL(
      recentReportsUrl("/api", { ids: ["06-0000051345", "06-0000023206"], minutes: 60 }),
      "http://naru.test",
    );
    expect(q.pathname).toBe("/api/reports/recent");
    expect(q.searchParams.get("ids")).toBe("06-0000051345,06-0000023206");
    expect(q.searchParams.get("minutes")).toBe("60");
    expect(parseRecentReports(recent.body).counts["06-0000023206"]).toEqual({
      blocked: 1,
      open: 0,
    });
    expect(() => parseRecentReports(near.body)).toThrow(NaruApiError);
  });

  it("행진 키프레임 (INTERFACE §3.2, T7.16) — URL, recorded 응답 파싱, 404 not_modeled 은 null", () => {
    expect(marchUrl("/api", "be5f89a4ebf3")).toBe("/api/closures/events/be5f89a4ebf3/march");
    const u = new URL(
      marchUrl("/api", "be5f89a4ebf3", { from: "2026-11-07T15:30:00+09:00" }),
      "http://naru.test",
    );
    expect(u.searchParams.get("from")).toBe("2026-11-07T15:30:00+09:00");
    expect(u.searchParams.get("to")).toBeNull();
    const rec = recorded("march_be5f89a4ebf3");
    const body = parseMarch(rec.body);
    expect(body.event_id).toBe("be5f89a4ebf3");
    expect(body.keyframes).toHaveLength(241); // 12:00~16:00 1분
    expect(Object.keys(body.crosswalk_points)).toHaveLength(13);
    expect(() => parseMarch(recorded("reports_recent").body)).toThrow(NaruApiError);
    const none = recorded("error_not_modeled");
    expect(none.status).toBe(404);
    expect(marchOrNull(new NaruApiError(none.status, none.body as ErrorBody))).toBeNull();
    expect(() => marchOrNull(new NaruApiError(500, null))).toThrow(NaruApiError);
  });
});
