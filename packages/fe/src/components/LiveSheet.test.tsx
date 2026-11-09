// 지금 서울 통제 (T7.5) — 렌더 테스트. Provider 초기 state 에 사건 v2 기록(scripts/record_live_events.py)을
// 넣고 그린다. 네트워크 없음 (CONVENTIONS §5.7-2). 기대값은 기록을 열어 확인한 사건 id·창·구
import { fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { createNaruApiClient } from "../api/naruApiClient";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider, type ClosureState } from "../state/ClosureProvider";
import { TimeProvider } from "../state/TimeProvider";
import { recordedClosures, recordedEvents, recordedLive } from "../test/recorded";
import { LiveSheet } from "./LiveSheet";

const fc0745 = recordedClosures("closures_0745");
const live0745 = recordedLive("closure_events_live_0315_0745");
// 목록 위 기준 시각은 실시간 돌발이 없던 기록으로 — 있으면 '지금'에 따라 경고가 바뀐다 (T5.9)
const dataAsOf = recordedEvents().data_as_of;

function Providers({
  children,
  live = live0745,
  state = {},
}: {
  children: ReactNode;
  live?: typeof live0745;
  state?: Partial<ClosureState>;
}) {
  const at = live.body.at;
  return (
    <ApiProvider client={createNaruApiClient("/api")}>
      <TimeProvider initialT={at}>
        <ClosureProvider
          fetchEnabled={false}
          initialState={{
            status: "ready",
            closures: fc0745,
            at,
            events: live.body.events,
            eventsAt: at,
            dataAsOf,
            ...state,
          }}
        >
          {children}
        </ClosureProvider>
      </TimeProvider>
    </ApiProvider>
  );
}

function group(name: string) {
  return within(screen.getByRole("region", { name }));
}

describe("LiveSheet — 지금 서울 통제", () => {
  it("3/15 07:45 — 제목·부제, 통제 중 9 → 1시간 안 시작 2 → 오늘 5, 행 배지는 남은 시간", () => {
    render(
      <Providers>
        <LiveSheet />
      </Providers>,
    );
    expect(screen.getByRole("region", { name: "3월 15일 07:45 서울 통제" })).toBeDefined();
    expect(screen.getByText(/서울 통제 중 9건, 예정 7건/)).toBeDefined();
    expect(group("통제 중").getAllByRole("button")).toHaveLength(9);
    expect(group("1시간 안 시작").getAllByRole("button")).toHaveLength(2);
    expect(group("오늘").getAllByRole("button")).toHaveLength(5);
    expect(screen.queryByRole("region", { name: "내일" })).toBeNull();
    expect(group("통제 중").getByText("23분 뒤 해제")).toBeDefined(); // 1구간 08:08
    expect(group("오늘").getByText("1시간 27분 뒤 시작")).toBeDefined(); // 10구간 09:12
    expect(screen.getByText("07:23–08:57 · 횡단보도 58곳")).toBeDefined(); // 2구간
    expect(screen.getByText("경찰청 11/6 공지 · 마라톤 3/12 시각표 기준")).toBeDefined();
    expect(screen.queryByRole("button", { name: "통제 불러오기" })).toBeNull();
  });

  it("행을 누르면 그 사건 카드(목록은 숨김), 닫으면 목록", () => {
    render(
      <Providers>
        <LiveSheet />
      </Providers>,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /^마라톤 1구간 세종대로 사거리~숭례문 오거리/ }),
    );
    const card = screen.getByRole("article", {
      name: "마라톤 1구간 세종대로 사거리~숭례문 오거리",
    });
    expect(within(card).getByText("08:08 해제 예정")).toBeDefined();
    expect(screen.queryByRole("region", { name: "통제 중" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "카드 닫기" }));
    expect(screen.queryByRole("article")).toBeNull();
    expect(group("통제 중").getAllByRole("button")).toHaveLength(9);
  });
});
