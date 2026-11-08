// 통제 불러오기 (T5.4) — 순수(날짜 묶음) + 렌더(Provider 초기 state 에 recorded 응답, 네트워크 없음).
// recorded naru_api/closure_events.json 을 열어 확인: 11/7 집회 2(15:00–16:00 31곳, 12:00–16:00 13곳),
// 3/15 마라톤 5(08:17·07:44·07:23·07:20·05:00 시작). 1구간 = 07:20–08:08 횡단보도 6곳
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { createNaruApiClient } from "../api/naruApiClient";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider, EMPTY_CLOSURES, useClosures } from "../state/ClosureProvider";
import { RouteProvider, odFromLocation, type RouteState } from "../state/RouteProvider";
import { TimeProvider, kstIso } from "../state/TimeProvider";
import { recorded, recordedEvents, recordedRoute } from "../test/recorded";
import { eventDays } from "./ClosureEvents";
import { ClosureSheet } from "./ClosureSheet";
import { RouteCard } from "./RouteCard";

const events = recordedEvents().events;
const T1330 = "2026-03-15T13:30:00+09:00";
const SEG1 = "마라톤 1구간 세종대로 사거리~숭례문 오거리";

function Providers({
  children,
  at,
  route = {},
}: {
  children: ReactNode;
  at: string;
  route?: Partial<RouteState>;
}) {
  return (
    <ApiProvider client={createNaruApiClient("/api")}>
      <TimeProvider initialT={at}>
        <ClosureProvider
          fetchEnabled={false}
          initialState={{ status: "ready", closures: EMPTY_CLOSURES, at, events }}
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

describe("통제 불러오기 렌더", () => {
  it("지금(통제 없음) → 빈 칸 안내 버튼 → 목록 → 3/15 1구간 → 07:20·지도 맞춤·목록 닫힘·제목 날짜 → '지금'", () => {
    render(
      <Providers at={kstIso(Date.now())}>
        <ClosureSheet />
        <FocusProbe />
      </Providers>,
    );
    expect(screen.getByText("오늘 통제")).toBeDefined();
    const empty = screen.getByText("이 시각에 걸린 통제가 없어요.");
    fireEvent.click(within(empty).getByRole("button", { name: "통제 불러오기" }));
    const list = screen.getByRole("region", { name: "통제 불러오기" });
    expect(within(list).getByText("11월 7일 (토)")).toBeDefined();
    expect(within(list).getByText("3월 15일 (일)")).toBeDefined();
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
    const header = screen.getAllByRole("button", { name: "통제 불러오기" })[0];
    if (!header) throw new Error("헤더 버튼");
    fireEvent.click(header);
    const list = screen.getByRole("region", { name: "통제 불러오기" });
    expect(
      within(list)
        .getAllByRole("button")
        .filter((b) => !b.hasAttribute("disabled")),
    ).toHaveLength(7);
    fireEvent.click(screen.getAllByRole("button", { name: "통제 불러오기" })[0] ?? header);
    expect(screen.queryByRole("region", { name: "통제 불러오기" })).toBeNull();
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
    fireEvent.click(within(list).getByRole("button", { name: /15:00~16:00 시의회~숭례문R/ }));
    expect(screen.getByText("15:00")).toBeDefined();
    expect(screen.getByText("2026-11-07")).toBeDefined();
    expect(screen.getByTestId("focus").textContent).toBe("none");
  });
});
