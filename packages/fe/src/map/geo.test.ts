// 표시용 거리 (T7.14 — 검색 결과마다 지도 가운데부터). 순수 수학 함수 — 점은 기록에서 읽는다
// (geocode_search_kyobo: 카카오 기록을 재생한 실제 Flask 응답, near = FE 기본 화면 가운데)
import { describe, expect, it } from "vitest";
import { parseGeocodeSearch, placeLngLat } from "../api/naruApiClient";
import { DEFAULT_BBOX } from "../state/ClosureProvider";
import { recorded } from "../test/recorded";
import { bboxCenter, distanceM } from "./geo";

describe("bboxCenter·distanceM (T7.14)", () => {
  it("기본 화면 가운데 = 기록할 때 보낸 near, 광화문교보빌딩 387 m·교보재단빌딩 630 m (pyproj WGS84 측지선 386.6·630.4)", () => {
    const rec = recorded("geocode_search_kyobo");
    const center = bboxCenter(DEFAULT_BBOX);
    const [lat, lng] = (rec.query?.["near"] ?? "").split(",").map(Number);
    expect(center?.[0]).toBeCloseTo(lng ?? 0, 6);
    expect(center?.[1]).toBeCloseTo(lat ?? 0, 6);
    const [kyobo, foundation] = parseGeocodeSearch(rec.body).places;
    const a = kyobo ? placeLngLat(kyobo) : null;
    const b = foundation ? placeLngLat(foundation) : null;
    expect(center && a ? Math.abs(distanceM(center, a) - 386.6) : 99).toBeLessThan(1.5);
    expect(center && b ? Math.abs(distanceM(center, b) - 630.4) : 99).toBeLessThan(2);
    expect(bboxCenter("1,2,3")).toBeNull();
  });
});
