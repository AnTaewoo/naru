// 장소 검색 (T5.8) — 순수(near) + 렌더(결과 목록). 입력은 recorded naru_api/geocode_search_*.json
// (record_naru_api.py 가 카카오 기록을 재생한 실제 Flask 응답). 검색 요청 자체는 e2e 에서 실제 BE 로
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { parseGeocodeSearch } from "../api/naruApiClient";
import { DEFAULT_BBOX } from "../state/ClosureProvider";
import { recorded } from "../test/recorded";
import { PlaceList, nearOf } from "./PlaceSearch";

const kyobo = parseGeocodeSearch(recorded("geocode_search_kyobo").body).places;

describe("장소 검색 (T5.8)", () => {
  it("near = 지도 가운데 lat,lng 소수 4자리 — 기본 범위면 기록할 때 보낸 값과 같다", () => {
    expect(nearOf(DEFAULT_BBOX)).toBe(recorded("geocode_search_kyobo").query?.["near"]);
    expect(nearOf("1,2,3")).toBeUndefined();
  });

  it("결과 줄 — 이름·주소·지도 가운데부터 거리, 줄을 누르면 그 장소 (T7.14 — 출발·도착은 장소 카드에서)", () => {
    const calls: string[] = [];
    // 기본 화면 가운데(기록 near) — 광화문교보빌딩 387m(측지선 386.6 m) · 교보재단빌딩 630m
    render(
      <PlaceList
        places={kyobo}
        center={[126.9775, 37.5675]}
        onChoose={(p) => calls.push(p.name)}
      />,
    );
    const rows = within(screen.getByRole("list", { name: "검색 결과" })).getAllByRole("listitem");
    expect(rows).toHaveLength(10);
    expect(rows[0]?.textContent).toContain("광화문교보빌딩");
    expect(rows[0]?.textContent).toContain("서울 종로구 종로 1");
    expect(rows[0]?.textContent).toContain("387m");
    expect(rows[1]?.textContent).toContain("630m");
    fireEvent.click(screen.getByRole("button", { name: "광화문교보빌딩 서울 종로구 종로 1" }));
    expect(calls).toEqual(["광화문교보빌딩"]);
    expect(screen.queryByRole("button", { name: "광화문교보빌딩 도착" })).toBeNull();
  });

  it("지도 가운데를 모르면 거리는 안 쓴다", () => {
    render(<PlaceList places={kyobo} center={null} onChoose={() => undefined} />);
    const rows = within(screen.getByRole("list", { name: "검색 결과" })).getAllByRole("listitem");
    expect(rows[0]?.textContent).not.toMatch(/\d+m$/);
  });
});
