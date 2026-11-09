// 서울 통제 시트 (T7.5 → T7.12 세 묶음) — 렌더 테스트. Provider 초기 state 에 사건 v2 기록(scripts/record_live_events.py)
// 을 넣고 그린다. 네트워크 없음 (CONVENTIONS §5.7-2). 기대값은 기록을 열어 확인한 사건 id·창·구
import { act, fireEvent, render, screen, within } from "@testing-library/react";
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
const live1109 = recordedLive("closure_events_live_1109_1330");
// 넓은 창(at 앞뒤 365일) — 시트 목록 (T7.12)
const catalog1107 = recordedLive("closure_events_catalog_1107_1530");
const catalog1108 = recordedLive("closure_events_catalog_1108_1200");
// 목록 위 기준 시각은 실시간 돌발이 없던 기록으로 — 있으면 '지금'에 따라 경고가 바뀐다 (T5.9)
const dataAsOf = recordedEvents().data_as_of;

type Live = typeof live0745;

function Providers({
  children,
  live = live0745,
  catalog = null,
  state = {},
}: {
  children: ReactNode;
  live?: Live | null;
  catalog?: Live | null;
  state?: Partial<ClosureState>;
}) {
  const at = (catalog ?? live)?.body.at ?? live0745.body.at;
  return (
    <ApiProvider client={createNaruApiClient("/api")}>
      <TimeProvider initialT={at}>
        <ClosureProvider
          fetchEnabled={false}
          initialState={{
            status: "ready",
            closures: fc0745,
            at,
            events: live?.body.events ?? null,
            eventsAt: live?.body.at ?? null,
            catalog: catalog?.body.events ?? null,
            catalogAt: catalog?.body.at ?? null,
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

function section(name: string) {
  return within(screen.getByRole("region", { name }));
}

describe("LiveSheet — 세 묶음 (T7.12)", () => {
  it("11/7 15:30 — 지금이 아니니 '11월 7일 15:30 기준', 이 시각 12 · 다가오는 11/9 다섯 · 지난 5 + 더 보기", () => {
    render(
      <Providers live={live1107} catalog={catalog1107}>
        <LiveSheet />
      </Providers>,
    );
    expect(screen.getByRole("region", { name: "서울 통제" })).toBeDefined();
    expect(screen.getByText("11월 7일 15:30 기준")).toBeDefined();
    expect(screen.getByRole("button", { name: "지금으로 돌아가기" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "지금 시각으로" })).toBeNull(); // 슬라이더 쪽은 숨김
    expect(section("이 시각").getAllByRole("button")).toHaveLength(12);
    const upcoming = section("다가오는 통제");
    expect(upcoming.getByText("11월 9일 (월)")).toBeDefined();
    expect(upcoming.getAllByRole("button")).toHaveLength(5);
    const past = section("지난 통제");
    expect(past.getAllByRole("button", { name: /^마라톤/ })).toHaveLength(5); // 3/15 15구간부터
    expect(past.getAllByRole("button")[0]?.textContent).toMatch(/3월 15일$/); // 지난 행 배지는 날짜
    fireEvent.click(past.getByRole("button", { name: "더 보기 (11)" }));
    expect(past.getAllByRole("button", { name: /^마라톤/ })).toHaveLength(16);
  });

  it("11/8 12:00 — 그 시각 걸린 통제가 없으면 한 줄 + 다가오는(내일)·지난 목록, 빈 화면이 아니다", () => {
    render(
      <Providers live={null} catalog={catalog1108}>
        <LiveSheet />
      </Providers>,
    );
    expect(section("이 시각").getByText("이 시각 서울에 걸린 통제가 없어요")).toBeDefined();
    expect(section("다가오는 통제").getByText("내일")).toBeDefined();
    expect(section("다가오는 통제").getAllByRole("button")).toHaveLength(5);
    expect(section("지난 통제").getByRole("button", { name: "더 보기 (23)" })).toBeDefined();
  });

  it("지난 행을 누르면 그 시작 시각으로 옮기고 카드 — 경찰청 r06 11/7 16:00", () => {
    render(
      <Providers live={null} catalog={catalog1108}>
        <LiveSheet />
      </Providers>,
    );
    act(() => {
      fireEvent.click(
        section("지난 통제").getByRole("button", { name: /^의사당역 5번출구 → 민주당사 행진/ }),
      );
    });
    expect(screen.getByRole("article", { name: "의사당역 5번출구 → 민주당사 행진" })).toBeDefined();
    expect(screen.getByText("11월 7일 16:00 기준")).toBeDefined(); // 카드 위에도 기준 줄
    fireEvent.click(screen.getByRole("button", { name: "카드 닫기" }));
    expect(screen.getByLabelText<HTMLInputElement>("날짜").value).toBe("2026-11-07");
    expect(screen.getByText("16:00")).toBeDefined();
  });

  it("지금으로 돌아가기 — 기준 시각이 지금이면 줄이 사라지고 제목이 '지금 서울 통제'", () => {
    render(
      <Providers live={live1107} catalog={catalog1107}>
        <LiveSheet />
      </Providers>,
    );
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "지금으로 돌아가기" }));
    });
    expect(screen.queryByRole("button", { name: "지금으로 돌아가기" })).toBeNull();
    expect(screen.getByRole("region", { name: "지금 서울 통제" })).toBeDefined();
  });
});

describe("LiveSheet — 행·카드·구 칩·묶음 (T7.5)", () => {
  it("3/15 07:45 — 목록을 아직 못 받으면 지도 사건으로, 부제·행 배지는 남은 시간", () => {
    render(
      <Providers>
        <LiveSheet />
      </Providers>,
    );
    expect(screen.getByText(/서울 통제 중 9건, 예정 7건/)).toBeDefined();
    expect(section("이 시각").getAllByRole("button")).toHaveLength(11); // 통제 중 9 + 1시간 안 2
    expect(section("이 시각").getByText("23분 뒤 해제")).toBeDefined(); // 1구간 08:08
    expect(section("다가오는 통제").getByText("1시간 27분 뒤 시작")).toBeDefined(); // 10구간 09:12
    expect(screen.getByText("07:23–08:57 · 횡단보도 58곳")).toBeDefined(); // 2구간
    expect(screen.queryByRole("button", { name: "통제 불러오기" })).toBeNull();
  });

  it("이 시각 행을 누르면 그 사건 카드(시각은 그대로), 닫으면 목록", () => {
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
    expect(screen.queryByRole("region", { name: "이 시각" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "카드 닫기" }));
    expect(screen.queryByRole("article")).toBeNull();
    expect(screen.getByText("07:45")).toBeDefined();
  });

  it("11/7 15:30 구 칩 — 화면과 겹치는 사건의 구 먼저, 영등포구를 고르면 세 묶음 모두 그 구만", () => {
    render(
      <Providers live={live1107} catalog={catalog1107}>
        <LiveSheet />
      </Providers>,
    );
    const chips = within(screen.getByRole("group", { name: "구 필터" }));
    // 넓은 창 기록의 사건 bbox 가 광화문 화면과 겹치는 수: 종로구 11·중구 9, 나머지 1씩(가나다), 안 겹치는 구는 뒤
    expect(chips.getAllByRole("button").map((b) => b.textContent)).toEqual([
      "전체",
      "종로구",
      "중구",
      "동대문구",
      "마포구",
      "서대문구",
      "성동구",
      "영등포구",
      "강남구",
      "광진구",
      "서초구",
      "송파구",
    ]);
    fireEvent.click(chips.getByRole("button", { name: "영등포구" }));
    // 이 시각: 돌발 여의대로 08:03 · 경찰청 r06 16:00 / 다가오는 11/9: 하나증권·지도 행진·돌발 국회대로
    expect(section("이 시각").getAllByRole("button")).toHaveLength(2);
    expect(section("다가오는 통제").getAllByRole("button")).toHaveLength(3);
    fireEvent.click(chips.getByRole("button", { name: "전체" }));
    expect(section("이 시각").getAllByRole("button")).toHaveLength(12);
  });

  it("지도에서 고른 묶음 — '여기 통제 2건'(흐린 0.65 도), 전체 보기로 돌아온다", () => {
    render(
      <Providers
        live={live1107}
        catalog={catalog1107}
        state={{ picked: ["159e13bfe71a", "3f036e3f24e0"] }}
      >
        <LiveSheet />
      </Providers>,
    );
    expect(screen.getByText("여기 통제 2건")).toBeDefined();
    expect(screen.queryByRole("group", { name: "구 필터" })).toBeNull();
    expect(screen.getByText("내자동사거리~사직공원 집회")).toBeDefined(); // r05 0.65 — 고른 묶음엔 보인다
    fireEvent.click(screen.getByRole("button", { name: "전체 보기" }));
    expect(screen.queryByText("여기 통제 2건")).toBeNull();
    expect(section("이 시각").getAllByRole("button")).toHaveLength(12);
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

describe("LiveSheet — 예시로 보기 (T7.11)", () => {
  it("시트 맨 아래 셋, 누르면 그 날짜·시각으로", () => {
    render(
      <Providers live={live1109}>
        <LiveSheet />
      </Providers>,
    );
    const examples = within(screen.getByRole("region", { name: "예시로 보기" }));
    expect(examples.getAllByRole("button").map((b) => b.textContent)).toEqual([
      "2026 서울마라톤3월 15일 07:45 광화문",
      "광화문 집회·행진11월 7일 15:00 세종대로",
      "국회대로 행진11월 9일 12:00",
    ]);
    fireEvent.click(examples.getByRole("button", { name: /2026 서울마라톤/ }));
    expect(screen.getByLabelText<HTMLInputElement>("날짜").value).toBe("2026-03-15");
    expect(screen.getByText("07:45")).toBeDefined();
  });
});
