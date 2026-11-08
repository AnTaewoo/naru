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
import { RoutePanel, coordLabel } from "./RoutePanel";

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

  it("LegList 07:45 — 레그 7행, 이름 있는 지하보도, 거리는 m 반올림", () => {
    const rows = legRows(r0745);
    expect(rows.map((r) => r.title)).toEqual([
      "보도",
      "계단",
      "광화문(세종문화회관) 지하보도",
      "계단",
      "보도",
      "횡단보도",
      "보도",
    ]);
    expect(rows[2]?.sub).toBe("지하보도");
    expect(rows[0]?.sub).toBeNull();
    expect(rows.map((r) => r.distance)).toEqual(["53m", "9m", "156m", "22m", "96m", "33m", "470m"]);
  });

  it("근거 07:45 — 사유 2묶음(해제 빠른 순), 시각표 게시·해제 예정, 확신도는 /closures 0.9", () => {
    const groups = evidenceGroups(r0745.avoided, fc0745, T745);
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
    expect(g1?.evidence.map((e) => [e.when, e.text, e.kind])).toEqual([
      ["3/12 16:07", "1구간 세종대로 사거리~숭례문 오거리", "timetable"],
      ["08:08", "확인 → 해제 예정", "timetable"],
    ]);
    expect(evidenceGroups(r1330.avoided, fc0745, T1330)).toEqual([]);
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
    expect(ev.textContent).toContain("이렇게 판단했어요");
    expect(ev.textContent).toContain("마라톤 1구간 세종대로 사거리~숭례문 오거리");
    expect(ev.textContent).toContain("23분 뒤 해제");
    expect(ev.textContent).toContain("3/12 16:07");
    expect(ev.textContent).toContain("확인 → 해제 예정");
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
    expect(screen.getByRole("region", { name: "통제 근거" }).textContent).toContain(
      "공지상 통제 시간 · 현장 확인 전",
    );
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
  it("출발·도착 좌표(위도, 경도 5자리)·탭 분, 바꾸기·뒤로", () => {
    render(
      <Providers at={T745} route={ready(r0745, T745)}>
        <RoutePanel />
      </Providers>,
    );
    const from = coordLabel(od.from ?? [0, 0]);
    const to = coordLabel(od.to ?? [0, 0]);
    expect(from).toBe("37.57097, 126.97790");
    expect(to).toBe("37.56504, 126.97654");
    expect(screen.getByRole("button", { name: `출발 ${from}` })).toBeDefined();
    expect(screen.getByRole("tab", { selected: true }).textContent).toContain("12분");
    fireEvent.click(screen.getByRole("button", { name: "출발·도착 바꾸기" }));
    expect(screen.getByRole("button", { name: `출발 ${to}` })).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "뒤로" }));
    expect(screen.getByRole("button", { name: "길찾기" })).toBeDefined(); // 홈의 길찾기 바로
    fireEvent.click(screen.getByRole("button", { name: "길찾기" }));
    expect(screen.getByText("지도를 눌러 출발을 고르세요")).toBeDefined();
  });
});
