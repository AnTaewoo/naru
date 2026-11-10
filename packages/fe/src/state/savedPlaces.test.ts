// ☆ 저장 (T7.14) — 이 기기에만(localStorage). 장소는 지오코딩 기록(geocode_search_kyobo)에서
import { describe, expect, it } from "vitest";
import { parseGeocodeSearch } from "../api/naruApiClient";
import { recorded } from "../test/recorded";
import { placePick } from "./RouteProvider";
import { SAVED_KEY, readSaved, toggleSaved, writeSaved } from "./savedPlaces";

describe("저장한 장소 (T7.14)", () => {
  it("저장하면 맨 앞, 다시 누르면 뺀다, 깨진 값은 빈 목록", () => {
    localStorage.removeItem(SAVED_KEY);
    const [a, b] = parseGeocodeSearch(recorded("geocode_search_kyobo").body)
      .places.slice(0, 2)
      .map(placePick);
    if (!a || !b) throw new Error("기록 장소 없음");
    expect(readSaved(localStorage)).toEqual([]);
    writeSaved(localStorage, toggleSaved(readSaved(localStorage), a));
    writeSaved(localStorage, toggleSaved(readSaved(localStorage), b));
    expect(readSaved(localStorage).map((p) => p.name)).toEqual(["교보재단빌딩", "광화문교보빌딩"]);
    writeSaved(localStorage, toggleSaved(readSaved(localStorage), a));
    expect(readSaved(localStorage).map((p) => p.name)).toEqual(["교보재단빌딩"]);
    localStorage.setItem(SAVED_KEY, "{broken");
    expect(readSaved(localStorage)).toEqual([]);
    expect(readSaved(null)).toEqual([]);
  });
});
