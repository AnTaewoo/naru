// 렌더 테스트 — Provider 초기 state 에 recorded 응답을 넣고 그린다. 네트워크 없음 (CONVENTIONS §5.7-2)
// T7.4: 시트 목록·시간표는 지금 지도 사건(사건 v2 기록, scripts/record_live_events.py)
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { createNaruApiClient } from "../api/naruApiClient";
import { COLORS } from "../map/colors";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider, useClosureDispatch, useClosures } from "../state/ClosureProvider";
import { TimeProvider } from "../state/TimeProvider";
import { recordedClosures, recordedEvents, recordedLive } from "../test/recorded";
import { ClosureSheet } from "./ClosureSheet";
import { timelineBars } from "./ClosureTimeline";
import { TimeSlider } from "./TimeSlider";

const T = "2026-03-15T07:45:00+09:00";
const fc0745 = recordedClosures("closures_0745");
const fc0430 = recordedClosures("closures_0430");
const live0745 = recordedLive("closure_events_live_0315_0745");
const live1107 = recordedLive("closure_events_live_1107_1530");
// 목록 위 기준 시각은 실시간 돌발이 없던 기록으로 — 있으면 '지금'에 따라 경고가 바뀐다 (T5.9)
const dataAsOf = recordedEvents().data_as_of;

function Providers({ children, live = live0745 }: { children: ReactNode; live?: typeof live0745 }) {
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
          }}
        >
          {children}
        </ClosureProvider>
      </TimeProvider>
    </ApiProvider>
  );
}

describe("timelineBars (순수)", () => {
  it("3/15 07:45 — 시트 목록과 같은 사건 16, 1구간 07:20~08:08 막대·통제 중 빨강", () => {
    const bars = timelineBars(live0745.body.events, live0745.atMs, "2026-03-15T00:00:00+09:00");
    expect(bars).toHaveLength(16);
    const seg1 = bars.find((b) => b.key === "adaea2f4cc02"); // 기록: marathon 1구간 07:20–08:08
    expect(seg1?.title).toBe("마라톤 1구간 세종대로 사거리~숭례문 오거리");
    expect(seg1?.color).toBe(COLORS.stop);
    expect(seg1?.leftPct).toBeCloseTo(((7 * 60 + 20) / (24 * 60)) * 100, 3);
    expect(seg1?.widthPct).toBeCloseTo((48 / (24 * 60)) * 100, 3);
    // 다른 날이면 막대 없음 — 3/15 사건을 3/16 축에
    expect(timelineBars(live0745.body.events, live0745.atMs, "2026-03-16T00:00:00+09:00")).toEqual(
      [],
    );
  });
});

describe("ClosureSheet", () => {
  it("3/15 07:45 — 부제는 서울 사건 수, 행·배지, 통제 불러오기는 없다", () => {
    render(
      <Providers>
        <ClosureSheet />
      </Providers>,
    );
    expect(screen.getByText("3월 15일 통제")).toBeDefined(); // 기준 시각이 오늘이 아니면 날짜 (T5.4)
    expect(screen.getByText(/서울 통제 중 9건, 예정 7건/)).toBeDefined(); // 칩과 같은 수
    expect(screen.getByText("마라톤 1구간 세종대로 사거리~숭례문 오거리")).toBeDefined();
    expect(screen.queryByText(/^marathon /)).toBeNull(); // 코드값은 화면에 안 나온다
    expect(screen.getByText("23분 뒤 해제")).toBeDefined(); // 1구간 08:08 해제, 07:45 기준
    expect(screen.getAllByText("제한")).toHaveLength(7); // 예정 행 배지
    expect(screen.getByText("07:23–08:57 · 횡단보도 58곳")).toBeDefined(); // 2구간, 기록 창 그대로
    expect(screen.queryByText(/확신/)).toBeNull();
    expect(screen.getByText("경찰청 11/6 공지 · 마라톤 3/12 시각표 기준")).toBeDefined();
    expect(screen.getByText("실시간 돌발(TOPIS)은 아직 받지 않아요")).toBeDefined();
    expect(screen.queryByRole("button", { name: "통제 불러오기" })).toBeNull(); // T7.4 삭제
    expect(screen.getByLabelText("기준 시각")).toBeDefined();
    expect(screen.getByText("07:45")).toBeDefined();
  });

  it("11/7 15:30 — 공지 행은 파서 제목·둘째 줄, 원문은 '공지 원문 보기'에서만, 0.65 는 목록에 없다", () => {
    render(
      <Providers live={live1107}>
        <ClosureSheet />
      </Providers>,
    );
    expect(screen.getByText(/서울 통제 중 8건, 예정 4건/)).toBeDefined();
    expect(screen.getByText("시의회~숭례문오거리 집회 → 광화문·고용노동청 행진")).toBeDefined();
    expect(screen.getByText("5만 명 · 태평로")).toBeDefined();
    expect(screen.getByText("15:00–16:00 · 횡단보도 22곳")).toBeDefined();
    expect(screen.queryByText(/내자/)).toBeNull(); // r05 내자R~사직공원 0.65 — 지도에만
    const excerpt =
      "15:00~16:00 시의회~숭례문R → 광화문·고용노동청 <태평로 등> 50,000명 중부, 종로, 남대문";
    expect(screen.queryByText(excerpt)).toBeNull(); // 목록엔 원문이 없다
    expect(document.querySelector(`[title="${excerpt}"]`)).toBeNull(); // 타임라인 툴팁에도
    const row = screen
      .getByText("시의회~숭례문오거리 집회 → 광화문·고용노동청 행진")
      .closest("div");
    if (!row) throw new Error("집회 행");
    const open = within(row).getByRole("button", { name: "공지 원문 보기" });
    fireEvent.click(open);
    expect(screen.getByText(excerpt)).toBeDefined();
    expect(open.getAttribute("aria-expanded")).toBe("true");
  });
});

function ClosureNudger() {
  const dispatch = useClosureDispatch();
  return (
    <button
      type="button"
      onClick={() => dispatch({ type: "receive", at: T, bbox: "x", closures: fc0430 })}
    >
      nudge
    </button>
  );
}

/** 대조군 — closures 를 읽는 컴포넌트는 nudge 에 다시 그려져야 한다 (아니면 아래 검사가 공허하다) */
function ClosureCount() {
  const { closures } = useClosures();
  return <span data-testid="closure-count">{closures.features.length}</span>;
}

// React 19 의 지연 컨텍스트 전파 때문에 Profiler.onRender 는 자식의 컨텍스트 재렌더를 놓친다 (2026-11-08 확인).
// 대신 TimeSlider 를 함수로 불러 그 훅들이 이 probe 에서 돌게 한다 → 구독 집합이 TimeSlider 와 같다
let sliderRenders = 0;
function SliderProbe() {
  sliderRenders += 1;
  return TimeSlider();
}

describe("TimeSlider 재렌더 격리", () => {
  it("closures state 가 바뀌어도 TimeSlider 는 다시 그려지지 않고, 슬라이더 조작엔 반응한다", () => {
    sliderRenders = 0;
    render(
      <Providers>
        <SliderProbe />
        <ClosureCount />
        <ClosureNudger />
      </Providers>,
    );
    expect(sliderRenders).toBe(1);
    expect(screen.getByTestId("closure-count").textContent).toBe("79");
    act(() => {
      fireEvent.click(screen.getByText("nudge"));
    });
    expect(screen.getByTestId("closure-count").textContent).toBe("5"); // closures 는 바뀌었다
    expect(sliderRenders).toBe(1); // 그래도 슬라이더는 그대로
    act(() => {
      fireEvent.change(screen.getByLabelText("기준 시각"), {
        target: { value: String(13 * 60 + 30) },
      });
    });
    expect(sliderRenders).toBe(2);
    expect(screen.getByText("13:30")).toBeDefined();
  });
});
