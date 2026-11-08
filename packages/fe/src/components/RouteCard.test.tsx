// 길찾기 화면 — 순수 함수(카드·레그·근거) + 렌더(Provider 초기 state 에 recorded 응답, 네트워크 없음)
// 기대값은 recorded naru_api/route_{0430,0745,1330,1107_1500}.json·closures_0745.json 을 열어 확인한 값:
// 07:45 경로 700 s·839.6 m(지하보도 1·횡단보도 1·계단 2), 원래 길 674 s·808.3 m, 피한 횡단보도 2곳(확인, 08:08·08:30 해제, 확신도 0.9)
// 13:30·04:30 경로 = 원래 길 674 s(횡단보도 레그 2), 피한 곳 없음 — 04:30 은 출발지 05:00 전이라 창 밖(ADR-011 A)
// 11/7 15:00 세종대로 935 s·1,122.5 m(시청 지하보도), 원래 길 871 s·1,044.9 m, 예정 1곳(16:00까지)
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { createNaruApiClient } from "../api/naruApiClient";
import { routeNoteKo } from "../i18n/ko";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider } from "../state/ClosureProvider";
import { RouteProvider, odFromLocation, type RouteState } from "../state/RouteProvider";
import { TimeProvider } from "../state/TimeProvider";
import { recorded, recordedClosures, recordedRoute } from "../test/recorded";
import type { ErrorBody, RouteResponse } from "../types/contracts";
import { evidenceGroups } from "./EvidencePopover";
import { legRows } from "./LegList";
import { RouteCard, fastestCard, originalCard, routeCrossing } from "./RouteCard";
import { RoutePanel } from "./RoutePanel";

const T745 = "2026-03-15T07:45:00+09:00";
const T1330 = "2026-03-15T13:30:00+09:00";
const T430 = "2026-03-15T04:30:00+09:00";
const r0745 = recordedRoute("route_0745");
const r1330 = recordedRoute("route_1330");
const r0430 = recordedRoute("route_0430");
const r1107 = recordedRoute("route_1107_1500");
const T1107 = "2026-11-07T15:00:00+09:00";
const fc0745 = recordedClosures("closures_0745");
const q = recorded("route_0745").query ?? {};
const od = odFromLocation(`?from=${q["from"] ?? ""}&to=${q["to"] ?? ""}`);

function Providers({
  children,
  at,
  route,
}: {
  children: ReactNode;
  at: string;
  route: Partial<RouteState>;
}) {
  return (
    <ApiProvider client={createNaruApiClient("/api")}>
      <TimeProvider initialT={at}>
        <ClosureProvider
          fetchEnabled={false}
          initialState={{ status: "ready", closures: fc0745, at }}
        >
          <RouteProvider
            fetchEnabled={false}
            initialState={{ active: true, from: od.from, to: od.to, ...route }}
          >
            {children}
          </RouteProvider>
        </ClosureProvider>
      </TimeProvider>
    </ApiProvider>
  );
}

function ready(route: RouteResponse, at: string): Partial<RouteState> {
  return { status: "ready", route, at };
}

describe("카드·레그·근거 (순수)", () => {
  it("07:45 가장 빠른 길 — 12분·840m·07:57 도착, 지하보도 1·횡단보도 1·계단 2", () => {
    expect(fastestCard(r0745, T745)).toEqual({
      minutes: 12,
      distance: "840m",
      arrive: "07:57",
      facts: [
        { kind: "underpass", count: 1 },
        { kind: "crosswalk", count: 1 },
        { kind: "stairs", count: 2 },
      ],
    });
    expect(routeCrossing(r0745)).toBe("광화문(세종문화회관) 지하보도");
  });

  it("07:45 원래 길 — 11분·808m, 확인 2곳이라 지금 못 감, 08:30 해제", () => {
    const orig = originalCard(r0745);
    expect(orig).toEqual({
      minutes: 11,
      distance: "808m",
      blocked: true,
      crosswalks: 2,
      confirmed: 2,
      scheduled: 0,
      until: "2026-03-15T08:30:00+09:00",
    });
    expect(
      routeNoteKo({
        ...(orig ?? { crosswalks: 0, until: null, blocked: false }),
        crossing: routeCrossing(r0745),
      }),
    ).toBe(
      "횡단보도 2곳이 08:30까지 막혀 있어 광화문(세종문화회관) 지하보도로 건너는 길을 골랐어요.",
    );
  });

  it("13:30·04:30 — 피한 통제가 없으면 원래 길 카드 없음 (04:30 은 창 밖이라 원래 길, ADR-011 A)", () => {
    expect(originalCard(r1330)).toBeNull();
    expect(fastestCard(r1330, T1330)).toMatchObject({ minutes: 11, arrive: "13:41" });
    expect(fastestCard(r1330, T1330).facts).toEqual([{ kind: "crosswalk", count: 2 }]);
    expect(originalCard(r0430)).toBeNull();
    expect(fastestCard(r0430, T430)).toMatchObject({
      minutes: 11,
      distance: "808m",
      arrive: "04:41",
    });
  });

  it("11/7 15:00 — 예정 집회 1곳(공지 창 안)을 시청 지하보도로 피함: 막힘은 아니고 공지상 통제 시간", () => {
    const orig = originalCard(r1107);
    expect(orig).toEqual({
      minutes: 15,
      distance: "1.0km",
      blocked: false,
      crosswalks: 1,
      confirmed: 0,
      scheduled: 1,
      until: "2026-11-07T16:00:00+09:00",
    });
    expect(fastestCard(r1107, T1107)).toMatchObject({
      minutes: 16,
      distance: "1.1km",
      arrive: "15:16",
    });
    expect(routeCrossing(r1107)).toBe("시청 지하보도");
    expect(
      routeNoteKo({
        ...(orig ?? { crosswalks: 0, until: null, blocked: false }),
        crossing: routeCrossing(r1107),
      }),
    ).toBe(
      "횡단보도 1곳이 16:00까지 공지상 통제 시간(현장 확인 전)이라 시청 지하보도로 건너는 길을 골랐어요.",
    );
  });

  it("LegList 07:45 — 레그 7행, 이름 있는 지하보도·횡단보도(교차로명, T5.10), 거리는 m 반올림", () => {
    const rows = legRows(r0745);
    expect(rows.map((r) => r.title)).toEqual([
      "보도",
      "계단",
      "광화문(세종문화회관) 지하보도",
      "계단",
      "보도",
      "청계광장", // recorded route_0745 legs[5].name — OA-23081 06-0000002137 교차로명
      "보도",
    ]);
    expect(rows[2]?.sub).toBe("지하보도");
    expect(rows[5]?.sub).toBe("횡단보도");
    expect(rows[0]?.sub).toBeNull();
    expect(rows.map((r) => r.distance)).toEqual(["53m", "9m", "156m", "22m", "96m", "33m", "470m"]);
  });

  it("근거 07:45 — 사유 2묶음(해제 빠른 순), 해제 시각·확신도(/closures 0.9), 출처 줄은 없다", () => {
    const groups = evidenceGroups(r0745.avoided, fc0745);
    expect(groups.map((g) => g.reason)).toEqual([
      "marathon 1구간 세종대로 사거리~숭례문 오거리",
      "marathon 출발지 광화문 광장 (미국대사관 앞 세종대로)",
    ]);
    const [g1] = groups;
    expect(g1).toMatchObject({
      status: "confirmed",
      type: "marathon",
      crosswalks: 1,
      confidence: 0.9,
    });
    expect(g1?.until).toBe("2026-03-15T08:08:00+09:00");
    expect(g1 && "evidence" in g1).toBe(false); // 원본 출처(공지·시각표 줄)는 쓰지 않는다 (태우 2026-11-08)
    expect(evidenceGroups(r1330.avoided, fc0745)).toEqual([]);
  });
});

describe("RouteCard 렌더", () => {
  it("07:45 — 카드 두 장·안내 문장, 경로 상세 → 레그 7행, 통제 근거 → 근거·확신도", () => {
    render(
      <Providers at={T745} route={ready(r0745, T745)}>
        <RouteCard />
      </Providers>,
    );
    const fast = screen.getByRole("article", { name: "가장 빠른 길" });
    expect(fast.textContent).toContain("가장 빠름");
    expect(fast.textContent).toContain("12분");
    expect(fast.textContent).toContain("840m · 07:57 도착");
    expect(fast.textContent).toContain("지하보도 1");
    expect(fast.textContent).toContain("계단 2");
    const orig = screen.getByRole("article", { name: "원래 길" });
    expect(orig.textContent).toContain("지금 못 감");
    expect(orig.textContent).toContain("11분");
    expect(orig.textContent).toContain("횡단보도 통제 중 2곳 · 08:30 해제");
    expect(
      screen.getByText(
        "횡단보도 2곳이 08:30까지 막혀 있어 광화문(세종문화회관) 지하보도로 건너는 길을 골랐어요.",
      ),
    ).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "경로 상세" }));
    const legs = screen.getByRole("list", { name: "경로 상세" });
    const items = within(legs).getAllByRole("listitem");
    expect(items).toHaveLength(7);
    expect(items[2]?.textContent).toContain("광화문(세종문화회관) 지하보도");
    expect(items[2]?.textContent).toContain("156m");

    fireEvent.click(screen.getByRole("button", { name: "통제 근거" }));
    const ev = screen.getByRole("region", { name: "통제 근거" });
    expect(ev.textContent).not.toContain("이렇게 판단했어요"); // 머리 없이 근거 줄만 (태우 2026-11-08)
    expect(ev.textContent).toContain("마라톤 1구간 세종대로 사거리~숭례문 오거리");
    expect(ev.textContent).toContain("~08:08 23분 뒤 해제"); // 해제 시각과 남은 시간 사이 띄어쓰기
    // 원본 출처 줄 없음 — 시각표 게시 시각·구간·[시각표] 칸 (태우 2026-11-08)
    expect(ev.textContent).not.toContain("3/12 16:07");
    expect(ev.textContent).not.toContain("시각표");
    expect(ev.textContent).not.toContain("해제 예정");
    expect(ev.textContent).not.toContain("→");
    expect(ev.textContent).toContain("확신도");
    expect(ev.textContent).toContain("0.90");
    expect(screen.queryByRole("list", { name: "경로 상세" })).toBeNull(); // 한 번에 하나
  });

  it("13:30 — 원래 길 카드·근거 버튼 없이 '걸린 통제 없음'", () => {
    render(
      <Providers at={T1330} route={ready(r1330, T1330)}>
        <RouteCard />
      </Providers>,
    );
    expect(screen.queryByRole("article", { name: "원래 길" })).toBeNull();
    expect(screen.queryByRole("button", { name: "통제 근거" })).toBeNull();
    expect(screen.getByText("이 시각엔 경로에 걸린 통제가 없어요.")).toBeDefined();
  });

  it("11/7 15:00 — 원래 길 카드·통제 근거가 '공지상 통제 시간 · 현장 확인 전'", () => {
    render(
      <Providers at={T1107} route={ready(r1107, T1107)}>
        <RouteCard />
      </Providers>,
    );
    const orig = screen.getByRole("article", { name: "원래 길" });
    expect(orig.textContent).toContain("공지상 통제 시간");
    expect(orig.textContent).toContain("횡단보도 공지상 통제 시간 1곳 · 현장 확인 전 · 16:00 해제");
    fireEvent.click(screen.getByRole("button", { name: "통제 근거" }));
    const ev = screen.getByRole("region", { name: "통제 근거" }).textContent ?? "";
    expect(ev).toContain("공지상 통제 시간 · 현장 확인 전");
    // 원본 출처 줄 없음 — "11/6 18:00 서울경찰청 집회 공지 [공지]"·"16:00 해제 예정 [공지]" (태우 2026-11-08)
    expect(ev).not.toContain("11/6 18:00");
    expect(ev).not.toContain("서울경찰청");
    expect(ev).not.toMatch(/공지$|공지확신|예정공지/);
    expect(ev).toContain("~16:00 1시간 뒤 해제");
    expect(ev).not.toContain("이렇게 판단했어요");
  });

  it("오류 — 그래프 밖(recorded error_out_of_coverage, 잠실)", () => {
    const err = recorded("error_out_of_coverage").body as ErrorBody;
    expect(err.error.code).toBe("out_of_coverage");
    render(
      <Providers
        at={T745}
        route={{ status: "error", error: err.error.message, errorCode: err.error.code }}
      >
        <RouteCard />
      </Providers>,
    );
    expect(screen.getByText("이 위치는 아직 길찾기 범위(종로·중구) 밖이에요")).toBeDefined();
  });

  it("오류 — 실제 Flask 오류 코드(invalid_query)를 한국어 문구로", () => {
    const err = recorded("error_invalid_query").body as ErrorBody;
    render(
      <Providers
        at={T745}
        route={{ status: "error", error: err.error.message, errorCode: err.error.code }}
      >
        <RouteCard />
      </Providers>,
    );
    expect(screen.getByText("출발·도착을 다시 골라 주세요")).toBeDefined();
    expect(screen.queryByRole("article", { name: "가장 빠른 길" })).toBeNull();
  });
});

describe("RoutePanel", () => {
  // 칸 이름 = recorded naru_api/geocode_reverse_{kyobo,daehanmun}.json 의 label (T5.8). 좌표는 안 보인다
  const fromName = (recorded("geocode_reverse_kyobo").body as { label: string }).label;
  const toName = (recorded("geocode_reverse_daehanmun").body as { label: string }).label;
  const names = {
    from: od.from ? { point: od.from, text: fromName } : null,
    to: od.to ? { point: od.to, text: toName } : null,
  };

  it("출발·도착 주소(좌표는 안 보임)·탭 분, 바꾸기·뒤로", () => {
    render(
      <Providers at={T745} route={{ ...ready(r0745, T745), names }}>
        <RoutePanel />
      </Providers>,
    );
    expect([fromName, toName]).toEqual(["종로구 종로 1", "중구 세종대로 99"]);
    expect(screen.getByRole("button", { name: "출발 종로구 종로 1" })).toBeDefined();
    const panel = screen.getByRole("region", { name: "출발·도착" });
    expect(panel.textContent).not.toMatch(/\d+\.\d{4}/); // 위경도 숫자 없음
    expect(screen.queryByRole("tablist")).toBeNull(); // 경로 종류가 하나라 탭 줄은 숨김 (T5.10)
    fireEvent.click(screen.getByRole("button", { name: "출발·도착 바꾸기" }));
    expect(screen.getByRole("button", { name: "출발 중구 세종대로 99" })).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "뒤로" }));
    expect(screen.getByRole("button", { name: "길찾기" })).toBeDefined(); // 홈의 길찾기 바로
    fireEvent.click(screen.getByRole("button", { name: "길찾기" }));
    // 다시 켜면 출발은 내 위치부터 찾는다 (T5.7) — 도착은 지도로
    expect(screen.getByRole("button", { name: "출발 내 위치 찾는 중…" })).toBeDefined();
    expect(screen.getByRole("button", { name: "도착 지도를 눌러 도착을 고르세요" })).toBeDefined();
  });

  it("내 위치 (T5.7) — 받은 칸은 '내 위치', 칸 옆 버튼은 그 칸을 찾는다(찾는 중 표시)", () => {
    render(
      <Providers at={T745} route={{ mine: od.from }}>
        <RoutePanel />
      </Providers>,
    );
    expect(screen.getByRole("button", { name: "출발 내 위치" })).toBeDefined();
    // 주소를 아직 못 받았으면(네트워크 없음) "선택한 위치" — 좌표는 쓰지 않는다 (T5.8)
    expect(screen.getByRole("button", { name: "도착 선택한 위치" })).toBeDefined();
    const toMine = screen.getByRole("button", { name: "도착을 내 위치로" });
    expect(toMine.getAttribute("aria-busy")).toBe("false");
    fireEvent.click(toMine);
    expect(screen.getByRole("button", { name: "도착 내 위치 찾는 중…" })).toBeDefined();
    expect(toMine.getAttribute("aria-busy")).toBe("true");
    expect(screen.getByRole("button", { name: "출발을 내 위치로" }).getAttribute("aria-busy")).toBe(
      "false",
    );
  });
});

describe("원래 길 보기 (T5.11)", () => {
  it("07:45 — 원래 길 카드를 누르면 원래 길을 고르고 시트가 접힌다, 가장 빠른 길 카드로 돌아온다", () => {
    render(
      <Providers at={T745} route={ready(r0745, T745)}>
        <RouteCard />
      </Providers>,
    );
    const fast = within(screen.getByRole("article", { name: "가장 빠른 길" })).getByRole("button");
    const orig = within(screen.getByRole("article", { name: "원래 길" })).getByRole("button");
    expect([fast.getAttribute("aria-pressed"), orig.getAttribute("aria-pressed")]).toEqual([
      "true",
      "false",
    ]);
    fireEvent.click(orig);
    expect([fast.getAttribute("aria-pressed"), orig.getAttribute("aria-pressed")]).toEqual([
      "false",
      "true",
    ]);
    // 지도에서 원래 길을 보도록 시트를 접는다 (T5.6 과 같은 규칙)
    expect(screen.getByRole("region", { name: "길찾기 결과" }).getAttribute("data-stage")).toBe(
      "collapsed",
    );
    expect(orig.textContent).toContain("지금 못 감"); // 카드 내용은 그대로
    fireEvent.click(fast);
    expect(fast.getAttribute("aria-pressed")).toBe("true");
  });

  it("13:30 — 피한 통제가 없으면 원래 길 카드가 없고 가장 빠른 길 카드도 누를 게 없다", () => {
    render(
      <Providers at={T1330} route={ready(r1330, T1330)}>
        <RouteCard />
      </Providers>,
    );
    const fast = screen.getByRole("article", { name: "가장 빠른 길" });
    expect(within(fast).queryByRole("button")).toBeNull();
    expect(screen.queryByRole("article", { name: "원래 길" })).toBeNull();
  });
});

describe("칸 입력 (T5.8)", () => {
  it("칸을 누르면 그 칸이 검색 입력칸 — 두 글자 전엔 안내, 닫기·Esc 로 돌아간다", () => {
    render(
      <Providers at={T745} route={{}}>
        <RoutePanel />
      </Providers>,
    );
    fireEvent.click(screen.getByRole("button", { name: "도착 선택한 위치" }));
    const input = screen.getByRole("searchbox", { name: "도착 검색" });
    expect(document.activeElement).toBe(input);
    expect(input.getAttribute("placeholder")).toBe("도착 검색 또는 지도 누르기");
    expect(screen.getByRole("status").textContent).toBe("두 글자 이상 입력하거나 지도를 누르세요");
    fireEvent.click(screen.getByRole("button", { name: "닫기" }));
    expect(screen.queryByRole("searchbox")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "출발 선택한 위치" }));
    fireEvent.keyDown(screen.getByRole("searchbox", { name: "출발 검색" }), { key: "Escape" });
    expect(screen.queryByRole("searchbox")).toBeNull();
  });

  it("홈 검색창 — 입력하면 결과 칸이 열리고 길찾기 버튼은 그대로", () => {
    render(
      <Providers at={T745} route={{ active: false, from: null, to: null }}>
        <RoutePanel />
      </Providers>,
    );
    const input = screen.getByRole("searchbox", { name: "장소·주소 검색" });
    fireEvent.change(input, { target: { value: "교" } });
    expect(screen.getByRole("status").textContent).toBe("두 글자 이상 입력하세요");
    expect(screen.getByRole("button", { name: "길찾기" })).toBeDefined();
  });
});

describe("내 위치 안내 (T5.7)", () => {
  const note = (route: Partial<RouteState>) => {
    const { unmount } = render(
      <Providers at={T745} route={{ from: null, ...route }}>
        <RouteCard />
      </Providers>,
    );
    const text = screen.getByRole("region", { name: "길찾기 결과" }).textContent ?? "";
    unmount();
    return text;
  };

  it("범위 밖·거부·실패 — 칸은 비우고 지도로 고르라고, 찾는 중엔 지도로 골라도 된다고", () => {
    expect(note({ locate: { which: "from", status: "outside" } })).toContain(
      "내 위치가 길찾기 범위(종로·중구) 밖이에요. 지도를 눌러 출발을 고르세요",
    );
    expect(note({ locate: { which: "from", status: "denied" } })).toContain(
      "위치 권한이 꺼져 있어요. 지도를 눌러 출발을 고르세요",
    );
    expect(note({ locate: { which: "to", status: "unavailable" } })).toContain(
      "내 위치를 찾지 못했어요. 지도를 눌러 도착을 고르세요",
    );
    expect(note({ locate: { which: "from", status: "locating" } })).toContain(
      "내 위치를 찾고 있어요. 지도를 눌러 출발을 골라도 돼요",
    );
    expect(note({})).toContain("지도를 눌러 출발·도착을 골라 주세요");
  });

  it("경로가 있어도 안내는 보인다 — 07:45 경로에서 도착을 내 위치로 했다가 거부", () => {
    const text = note({
      from: od.from,
      status: "ready",
      route: r0745,
      at: T745,
      locate: { which: "to", status: "denied" },
    });
    expect(text).toContain("위치 권한이 꺼져 있어요. 지도를 눌러 도착을 고르세요");
    expect(text).toContain("12분");
  });
});
