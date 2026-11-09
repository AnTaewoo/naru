// 통제 불러오기 (T5.4) — 순수(날짜 묶음) + 렌더(Provider 초기 state 에 recorded 응답, 네트워크 없음).
// recorded naru_api/closure_events.json 을 열어 확인: 11/7 집회 2(15:00–16:00 31곳, 12:00–16:00 13곳),
// 3/15 마라톤 5(08:17·07:44·07:23·07:20·05:00 시작). 1구간 = 07:20–08:08 횡단보도 6곳
// T6.9 서울 전체 — recorded naru_api/closure_events_seoul.json 을 열어 확인: 사건 27, 구별 사건 수
// 종로구 9·중구 8·송파구 6·광진구 5·성동구 5·영등포구 3·동대문구 2·서초구 1
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { createNaruApiClient } from "../api/naruApiClient";
import { ApiProvider } from "../state/ApiProvider";
import {
  ClosureProvider,
  DEFAULT_BBOX,
  EMPTY_CLOSURES,
  asBbox4,
  eventBbox,
  useClosures,
} from "../state/ClosureProvider";
import { RouteProvider, odFromLocation, type RouteState } from "../state/RouteProvider";
import { TimeProvider, kstIso } from "../state/TimeProvider";
import { recorded, recordedEvents, recordedRoute } from "../test/recorded";
import type { ClosureEvent } from "../types/contracts";
import { byDistrict, districtChips, eventDays, eventGroups } from "./ClosureEvents";
import { ClosureSheet } from "./ClosureSheet";
import { RouteCard } from "./RouteCard";

const events = recordedEvents().events;
const seoul = recordedEvents("closure_events_seoul").events;
const T1330 = "2026-03-15T13:30:00+09:00";
const SEG1 = "마라톤 1구간 세종대로 사거리~숭례문 오거리";

function Providers({
  children,
  at,
  route = {},
  list = events,
}: {
  children: ReactNode;
  at: string;
  route?: Partial<RouteState>;
  list?: ClosureEvent[];
}) {
  return (
    <ApiProvider client={createNaruApiClient("/api")}>
      <TimeProvider initialT={at}>
        <ClosureProvider
          fetchEnabled={false}
          initialState={{ status: "ready", closures: EMPTY_CLOSURES, at, events: list }}
        >
          <RouteProvider fetchEnabled={false} initialState={route}>
            {children}
          </RouteProvider>
        </ClosureProvider>
      </TimeProvider>
    </ApiProvider>
  );
}

/** 지도 맞춤 요청을 글자로 — MapView 는 jsdom 에서 못 그리니 상태를 본다 */
function FocusProbe() {
  const { focus } = useClosures();
  return <span data-testid="focus">{focus ? `${focus.seq}:${focus.bbox.join(",")}` : "none"}</span>;
}

/** 헤더 버튼으로 목록을 연다 */
function openList(): HTMLElement {
  const header = screen.getAllByRole("button", { name: "통제 불러오기" })[0];
  if (!header) throw new Error("헤더 버튼");
  fireEvent.click(header);
  return screen.getByRole("region", { name: "통제 불러오기" });
}

/** 접힌 "지난 통제 N건" 을 편다 — 없으면(전부 오늘·다가오는 것) 그대로 */
function openPast(list: HTMLElement) {
  const toggle = within(list).queryByRole("button", { name: /^지난 통제/ });
  if (toggle?.getAttribute("aria-expanded") === "false") fireEvent.click(toggle);
}

describe("eventDays (순수)", () => {
  it("사건 7개 → 날짜 둘, 최근 날짜 먼저, 날짜 안은 API 순서(시작 늦은 순)", () => {
    const days = eventDays(events);
    expect(days.map((d) => d.label)).toEqual(["11월 7일 (토)", "3월 15일 (일)"]);
    expect(days[0]?.events.map((e) => e.crosswalks)).toEqual([31, 13]);
    expect(days[1]?.events).toHaveLength(5);
    expect(days[1]?.events.at(-1)?.reason).toBe(
      "marathon 출발지 광화문 광장 (미국대사관 앞 세종대로)",
    );
  });
});

describe("eventGroups (순수, T5.9 · T6.9)", () => {
  it("오늘·다가오는(진행 중 포함) 것 먼저 시작 순, 어제까지 끝난 건 '지난 통제' — 기준은 실제 지금", () => {
    // 11/7 13:00 이면 12:00~16:00 은 진행 중, 15:00~16:00 은 다가옴, 3/15 마라톤은 지남
    const mid = eventGroups(events, Date.parse("2026-11-07T13:00:00+09:00"));
    expect(mid.upcoming.flatMap((d) => d.events.map((e) => e.window.start))).toEqual([
      "2026-11-07T12:00:00+09:00",
      "2026-11-07T15:00:00+09:00",
    ]);
    expect(mid.past.map((d) => d.label)).toEqual(["3월 15일 (일)"]);
    // 11/7 17:00 — 둘 다 16:00 에 끝났지만 오늘 통제라 오늘 묶음에 그대로 (T6.9 "오늘·다가오는 것만 펼침")
    const evening = eventGroups(events, Date.parse("2026-11-07T17:00:00+09:00"));
    expect(evening.upcoming.map((d) => d.label)).toEqual(["11월 7일 (토)"]);
    expect(evening.upcoming[0]?.events.map((e) => e.crosswalks)).toEqual([13, 31]);
    expect(evening.past.map((d) => d.label)).toEqual(["3월 15일 (일)"]);
    // 11/8 16:00(기록한 날) 이면 전부 지난 통제 — 최근 날짜 먼저
    const later = eventGroups(events, Date.parse("2026-11-08T16:00:00+09:00"));
    expect(later.upcoming).toEqual([]);
    expect(later.past.map((d) => d.label)).toEqual(["11월 7일 (토)", "3월 15일 (일)"]);
  });
});

describe("구 칩 (순수, T6.9)", () => {
  it("지도 화면과 bbox 가 겹치는 사건의 구 먼저(그 사건 수 많은 순), 나머지는 가나다", () => {
    // 기본 화면(광화문 일대)과 겹치는 사건: 종로구 9·중구 8, 3구간(성동)·4구간(동대문)이 걸쳐 1씩
    const view = asBbox4(DEFAULT_BBOX.split(",").map(Number));
    expect(districtChips(seoul, view)).toEqual([
      "종로구",
      "중구",
      "동대문구",
      "성동구",
      "광진구",
      "서초구",
      "송파구",
      "영등포구",
    ]);
    // 화면을 마라톤 12구간(잠실역~송파역) 범위로 — 겹치는 건 12·13구간(송파구)뿐
    const jamsil = seoul.find((e) => e.reason.includes("12구간"));
    expect(districtChips(seoul, jamsil ? eventBbox(jamsil) : null)).toEqual([
      "송파구",
      "광진구",
      "동대문구",
      "서초구",
      "성동구",
      "영등포구",
      "종로구",
      "중구",
    ]);
  });

  it("구를 고르면 그 구를 지나는 사건만 — 영등포구 3건(11/9 하나증권·11/7 의사당역·여의대로)", () => {
    expect(byDistrict(seoul, null)).toHaveLength(27);
    expect(byDistrict(seoul, "영등포구").map((e) => e.window.start)).toEqual([
      "2026-11-09T10:30:00+09:00",
      "2026-11-07T16:00:00+09:00",
      "2026-11-07T08:03:00+09:00",
    ]);
  });
});

describe("통제 불러오기 렌더", () => {
  it("지금(통제 없음) → 빈 칸 안내 버튼 → 목록(지난 통제는 접힘) → 펴서 3/15 1구간 → 07:20·지도 맞춤·목록 닫힘·제목 날짜 → '지금'", () => {
    render(
      <Providers at={kstIso(Date.now())}>
        <ClosureSheet />
        <FocusProbe />
      </Providers>,
    );
    expect(screen.getByText("오늘 통제")).toBeDefined();
    // 기준 시각이 실제 지금이면 '지금' 배지, 지금으로 돌아가는 버튼은 없다 (T5.9)
    expect(screen.getByText("지금")).toBeDefined();
    expect(screen.queryByRole("button", { name: "지금 시각으로" })).toBeNull();
    const empty = screen.getByText("이 시각에 걸린 통제가 없어요.");
    fireEvent.click(within(empty).getByRole("button", { name: "통제 불러오기" }));
    const list = screen.getByRole("region", { name: "통제 불러오기" });
    // 기록은 전부 지난 일 — 오늘·다가오는 건 없다고 말하고, 지난 7건은 접혀 있다 (T6.9)
    expect(within(list).getByText("오늘·다가오는 통제가 없어요.")).toBeDefined();
    const toggle = within(list).getByRole("button", { name: "지난 통제 7건" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(within(list).queryByText("11월 7일 (토)")).toBeNull();
    fireEvent.click(toggle);
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    const past = within(list).getByRole("group", { name: "지난 통제" });
    expect(within(past).getByText("11월 7일 (토)")).toBeDefined();
    expect(within(past).getByText("3월 15일 (일)")).toBeDefined();
    expect(
      within(past).getByText("시의회~숭례문오거리 집회 → 광화문·고용노동청 행진"),
    ).toBeDefined();
    expect(within(past).getAllByText("5만 명 · 태평로").length).toBeGreaterThan(0);
    fireEvent.click(within(list).getByRole("button", { name: new RegExp(SEG1) }));
    expect(screen.getByText("07:20")).toBeDefined();
    expect(screen.getByText("2026-03-15")).toBeDefined();
    const seg1 = events.find((e) => e.reason.includes("1구간"));
    expect(screen.getByTestId("focus").textContent).toBe(`1:${seg1?.bbox.join(",") ?? ""}`);
    expect(screen.queryByRole("region", { name: "통제 불러오기" })).toBeNull();
    expect(screen.getByText("3월 15일 통제")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "지금 시각으로" }));
    expect(screen.getByText("오늘 통제")).toBeDefined();
    expect(screen.getByText(kstIso(Date.now()).slice(0, 10))).toBeDefined();
  });

  it("헤더 버튼으로도 열고 닫는다, 시작 없는 사건은 없다(기록 7개 모두 시작 있음)", () => {
    render(
      <Providers at={T1330}>
        <ClosureSheet />
      </Providers>,
    );
    const list = openList();
    openPast(list);
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(7);
    expect(rows.filter((r) => within(r).getByRole("button").hasAttribute("disabled"))).toEqual([]);
    fireEvent.click(screen.getAllByRole("button", { name: "통제 불러오기" })[0] ?? list);
    expect(screen.queryByRole("region", { name: "통제 불러오기" })).toBeNull();
  });

  it("서울 전체 — 구 칩은 지도 화면 안의 구 먼저, 고르면 그 구 통제만(지난 것 포함), '전체'로 돌아온다", () => {
    render(
      <Providers at={T1330} list={seoul}>
        <ClosureSheet />
      </Providers>,
    );
    const list = openList();
    const chips = within(list).getByRole("group", { name: "구 필터" });
    expect(
      within(chips)
        .getAllByRole("button")
        .map((b) => b.textContent),
    ).toEqual([
      "전체",
      "종로구",
      "중구",
      "동대문구",
      "성동구",
      "광진구",
      "서초구",
      "송파구",
      "영등포구",
    ]);
    const all = within(chips).getByRole("button", { name: "전체" });
    expect(all.getAttribute("aria-pressed")).toBe("true");
    const ydp = within(chips).getByRole("button", { name: "영등포구" });
    fireEvent.click(ydp);
    expect(ydp.getAttribute("aria-pressed")).toBe("true");
    expect(all.getAttribute("aria-pressed")).toBe("false");
    openPast(list);
    expect(within(list).getAllByRole("listitem")).toHaveLength(3);
    // 11/7 16:00 사건 요약 segments [의사당역 5번출구 → 민주당사], type march → ko.ts eventTitleKo
    expect(within(list).getByText("의사당역 5번출구 → 민주당사 행진")).toBeDefined();
    fireEvent.click(all);
    expect(within(list).getAllByRole("listitem")).toHaveLength(27);
  });

  it("길찾기 시트 — 걸린 통제가 없으면 안내에 버튼, 고르면 시각만 바뀌고 지도는 경로 그대로", () => {
    const q = recorded("route_1330").query ?? {};
    const od = odFromLocation(`?from=${q["from"] ?? ""}&to=${q["to"] ?? ""}`);
    render(
      <Providers
        at={T1330}
        route={{
          active: true,
          ...od,
          status: "ready",
          route: recordedRoute("route_1330"),
          at: T1330,
        }}
      >
        <RouteCard />
        <FocusProbe />
      </Providers>,
    );
    const note = screen.getByText("이 시각엔 경로에 걸린 통제가 없어요.");
    fireEvent.click(within(note).getByRole("button", { name: "통제 불러오기" }));
    const list = screen.getByRole("region", { name: "통제 불러오기" });
    openPast(list);
    fireEvent.click(
      within(list).getByRole("button", {
        name: /시의회~숭례문오거리 집회 → 광화문·고용노동청 행진/,
      }),
    );
    expect(screen.getByText("15:00")).toBeDefined();
    expect(screen.getByText("2026-11-07")).toBeDefined();
    expect(screen.getByTestId("focus").textContent).toBe("none");
  });
});
