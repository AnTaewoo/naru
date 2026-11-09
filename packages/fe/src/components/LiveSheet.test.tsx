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
const live1107 = recordedLive("closure_events_live_1107_1530");
const live1108 = recordedLive("closure_events_live_1108_2000");
const live1109 = recordedLive("closure_events_live_1109_1330");
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

  it("11/7 15:30 구 칩 — 종로구·중구 먼저, 영등포구를 고르면 그 사건 둘만, '전체'로 돌아온다", () => {
    render(
      <Providers live={live1107}>
        <LiveSheet />
      </Providers>,
    );
    const chips = within(screen.getByRole("group", { name: "구 필터" }));
    expect(chips.getAllByRole("button").map((b) => b.textContent)).toEqual([
      "전체",
      "종로구",
      "중구",
      "강남구",
      "서초구",
      "영등포구",
    ]);
    fireEvent.click(chips.getByRole("button", { name: "영등포구" }));
    // 돌발 여의대로 08:03(통제 중) · 경찰청 r06 의사당역 16:00(1시간 안)
    expect(group("통제 중").getAllByRole("button")).toHaveLength(1);
    expect(group("1시간 안 시작").getAllByRole("button")).toHaveLength(1);
    fireEvent.click(chips.getByRole("button", { name: "전체" }));
    expect(group("통제 중").getAllByRole("button")).toHaveLength(8);
  });

  it("11/8 20:00 — 다음 날 11/9 통제 다섯은 '내일'", () => {
    render(
      <Providers live={live1108}>
        <LiveSheet />
      </Providers>,
    );
    expect(group("내일").getAllByRole("button")).toHaveLength(5);
    expect(group("내일").getByText("국회의사당앞 → 효자동삼거리 행진")).toBeDefined();
  });

  it("지도에서 고른 묶음 — '여기 통제 2건'(흐린 0.65 도), 전체 보기로 돌아온다", () => {
    render(
      <Providers live={live1107} state={{ picked: ["159e13bfe71a", "3f036e3f24e0"] }}>
        <LiveSheet />
      </Providers>,
    );
    expect(screen.getByText("여기 통제 2건")).toBeDefined();
    expect(screen.queryByRole("group", { name: "구 필터" })).toBeNull();
    expect(screen.getByText("내자동사거리~사직공원 집회")).toBeDefined(); // r05 0.65 — 고른 묶음엔 보인다
    fireEvent.click(screen.getByRole("button", { name: "전체 보기" }));
    expect(screen.queryByText("여기 통제 2건")).toBeNull();
    expect(group("통제 중").getAllByRole("button")).toHaveLength(8);
  });

  it("고른 사건(?event=·지도)이면 처음부터 그 카드", () => {
    render(
      <Providers live={live1109} state={{ selected: "ccaa9980c6ac" }}>
        <LiveSheet />
      </Providers>,
    );
    expect(screen.getByRole("article", { name: "국회의사당앞 → 효자동삼거리 행진" })).toBeDefined();
  });
});
