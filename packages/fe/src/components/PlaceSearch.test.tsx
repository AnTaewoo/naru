// 장소 검색 (T5.8) — 순수(near) + 렌더(결과 목록). 입력은 recorded naru_api/geocode_search_*.json
// (record_naru_api.py 가 카카오 기록을 재생한 실제 Flask 응답). 검색 요청 자체는 e2e 에서 실제 BE 로
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { parseGeocodeSearch } from "../api/naruApiClient";
import { DEFAULT_BBOX } from "../state/ClosureProvider";
import type { OdField } from "../state/RouteProvider";
import { recorded } from "../test/recorded";
import { PlaceList, nearOf } from "./PlaceSearch";

const kyobo = parseGeocodeSearch(recorded("geocode_search_kyobo").body).places;

describe("장소 검색 (T5.8)", () => {
  it("near = 지도 가운데 lat,lng 소수 4자리 — 기본 범위면 기록할 때 보낸 값과 같다", () => {
    expect(nearOf(DEFAULT_BBOX)).toBe(recorded("geocode_search_kyobo").query?.["near"]);
    expect(nearOf("1,2,3")).toBeUndefined();
  });

  it("홈 결과 — 장소마다 이름·주소와 '출발'·'도착'", () => {
    const calls: [string, OdField][] = [];
    render(<PlaceList places={kyobo} which={null} onChoose={(p, w) => calls.push([p.name, w])} />);
    const rows = within(screen.getByRole("list", { name: "검색 결과" })).getAllByRole("listitem");
    expect(rows).toHaveLength(10);
    expect(rows[0]?.textContent).toContain("광화문교보빌딩");
    expect(rows[0]?.textContent).toContain("서울 종로구 종로 1");
    fireEvent.click(screen.getByRole("button", { name: "광화문교보빌딩 도착" }));
    fireEvent.click(screen.getByRole("button", { name: "교보재단빌딩 출발" }));
    expect(calls).toEqual([
      ["광화문교보빌딩", "to"],
      ["교보재단빌딩", "from"],
    ]);
  });

  it("칸 결과 — 줄을 누르면 그 칸에", () => {
    const calls: [string, OdField][] = [];
    render(<PlaceList places={kyobo} which="from" onChoose={(p, w) => calls.push([p.name, w])} />);
    fireEvent.click(screen.getByRole("button", { name: "광화문교보빌딩 서울 종로구 종로 1" }));
    expect(calls).toEqual([["광화문교보빌딩", "from"]]);
    expect(screen.queryByRole("button", { name: "광화문교보빌딩 도착" })).toBeNull();
  });
});
