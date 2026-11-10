// 검색한 장소 카드 (T7.14) — 렌더. 장소는 지오코딩 기록(geocode_search_kyobo, 카카오 기록 재생), 네트워크 없음
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { createNaruApiClient, parseGeocodeSearch } from "../api/naruApiClient";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider } from "../state/ClosureProvider";
import { RouteProvider, placePick, useRoute, type PlacePick } from "../state/RouteProvider";
import { SAVED_KEY } from "../state/savedPlaces";
import { TimeProvider } from "../state/TimeProvider";
import { recorded } from "../test/recorded";
import { PlaceCard } from "./PlaceCard";

const [first] = parseGeocodeSearch(recorded("geocode_search_kyobo").body).places;
const kyobo: PlacePick | null = first ? placePick(first) : null;

function Providers({ children }: { children: ReactNode }) {
  return (
    <ApiProvider client={createNaruApiClient("/api")}>
      <TimeProvider initialT="2026-03-15T07:45:00+09:00">
        <ClosureProvider fetchEnabled={false}>
          <RouteProvider fetchEnabled={false} initialState={{ place: kyobo }}>
            {children}
          </RouteProvider>
        </ClosureProvider>
      </TimeProvider>
    </ApiProvider>
  );
}

function Probe() {
  const r = useRoute();
  return (
    <output aria-label="길찾기 상태">{`${String(r.active)} ${r.from?.join(",") ?? "-"} ${r.place?.name ?? "-"}`}</output>
  );
}

describe("PlaceCard (T7.14)", () => {
  it("이름·도로명 주소·[출발][도착][☆ 저장] — 출발을 누르면 길찾기 출발, 장소 카드는 닫힌다", () => {
    render(
      <Providers>
        <PlaceCard />
        <Probe />
      </Providers>,
    );
    const card = screen.getByRole("article", { name: "광화문교보빌딩" });
    expect(card.textContent).toContain("서울 종로구 종로 1");
    fireEvent.click(screen.getByRole("button", { name: "출발" }));
    expect(screen.getByLabelText("길찾기 상태").textContent).toBe(
      "true 126.9779039768265,37.5709686446227 -",
    );
  });

  it("☆ 저장 → ★ 저장됨(이 기기 localStorage), 닫기 → 장소 없음", () => {
    localStorage.removeItem(SAVED_KEY);
    render(
      <Providers>
        <PlaceCard />
        <Probe />
      </Providers>,
    );
    fireEvent.click(screen.getByRole("button", { name: "☆ 저장" }));
    expect(screen.getByRole("button", { name: "★ 저장됨" })).toBeDefined();
    expect(localStorage.getItem(SAVED_KEY)).toContain("광화문교보빌딩");
    fireEvent.click(screen.getByRole("button", { name: "장소 닫기" }));
    expect(screen.getByLabelText("길찾기 상태").textContent).toBe("false - -");
  });
});
