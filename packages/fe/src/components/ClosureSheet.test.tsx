// 렌더 테스트 — Provider 초기 state 에 recorded 응답을 넣고 그린다. 네트워크 없음 (CONVENTIONS §5.7-2)
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { createNaruApiClient } from "../api/naruApiClient";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider, useClosureDispatch, useClosures } from "../state/ClosureProvider";
import { TimeProvider } from "../state/TimeProvider";
import { recordedClosures, recordedEvents } from "../test/recorded";
import { ClosureSheet, closureRows, withEvents } from "./ClosureSheet";
import { timelineBars } from "./ClosureTimeline";
import { TimeSlider } from "./TimeSlider";

const T = "2026-03-15T07:45:00+09:00";
const fc0745 = recordedClosures("closures_0745");
const fc0430 = recordedClosures("closures_0430");
const fc1107 = recordedClosures("closures_1107_1500"); // 11/7 15:00 광화문 — 공지 집회 두 건
const T1107 = "2026-11-07T15:00:00+09:00";
const { events, data_as_of: dataAsOf } = recordedEvents(); // v0.12 — 사건 칸·기준 시각

function Providers({
  children,
  at = T,
  closures = fc0745,
}: {
  children: ReactNode;
  at?: string;
  closures?: typeof fc0745;
}) {
  return (
    <ApiProvider client={createNaruApiClient("/api")}>
      <TimeProvider initialT={at}>
        <ClosureProvider
          fetchEnabled={false}
          initialState={{ status: "ready", closures, at, events, dataAsOf }}
        >
          {children}
        </ClosureProvider>
      </TimeProvider>
    </ApiProvider>
  );
}

describe("closureRows / timelineBars (순수)", () => {
  it("07:45 — 횡단보도 79개가 후보 단위 행으로 묶이고 확인이 먼저 온다", () => {
    const rows = closureRows(fc0745);
    expect(rows.reduce((n, r) => n + r.crosswalks, 0)).toBe(79);
    expect(rows.length).toBeGreaterThan(1);
    expect(rows[0]?.status).toBe("confirmed");
    const seg1 = rows.find((r) => r.reason.includes("1구간"));
    expect(seg1?.status).toBe("confirmed");
    expect(seg1?.start).toBe("2026-03-15T07:20:00+09:00");
    expect(seg1?.end).toBe("2026-03-15T08:08:00+09:00");
    expect(seg1 && "evidence" in seg1).toBe(false); // 출처 줄(시각표·확신)은 쓰지 않는다 (T5.9)
    const bars = timelineBars(fc0745, "2026-03-15T00:00:00+09:00");
    expect(bars).toHaveLength(rows.length);
    const seg1bar = bars.find((b) => b.reason.includes("1구간"));
    expect(seg1bar?.leftPct).toBeCloseTo(((7 * 60 + 20) / (24 * 60)) * 100, 3);
    expect(seg1bar?.widthPct).toBeCloseTo((48 / (24 * 60)) * 100, 3);
  });
  it("횡단보도 수는 화면 영역 말고 사건 전체 — 07:45 2구간 화면 안 23곳 → 58곳 (T5.9)", () => {
    const rows = withEvents(closureRows(fc0745), events);
    const count = (part: string) => rows.find((r) => r.reason.includes(part))?.crosswalks;
    // recorded closures_0745 의 화면 안 개수 23·21·24 → closure_events 의 사건 전체 58·54·60
    expect([count("2구간"), count("3구간"), count("4구간"), count("1구간")]).toEqual([
      58, 54, 60, 6,
    ]);
    // 11/7 r04: 구간 후보가 겹쳐 피처 38개지만 서로 다른 횡단보도 31곳
    const rally = withEvents(closureRows(fc1107), events).find((r) => r.reason.startsWith("15:00"));
    expect(rally?.crosswalks).toBe(31);
    expect(rally?.event?.summary?.reported_people).toBe(50000);
  });
  it("04:30 — 예정 1행(출발지 구간), 횡단보도 5곳", () => {
    const rows = closureRows(fc0430);
    expect(rows).toHaveLength(1);
    expect(rows[0]?.status).toBe("scheduled");
    expect(rows[0]?.crosswalks).toBe(5);
  });
});

describe("ClosureSheet", () => {
  it("recorded 07:45 를 그린다 — 부제 개수·행·배지", () => {
    render(
      <Providers>
        <ClosureSheet />
      </Providers>,
    );
    expect(screen.getByText("3월 15일 통제")).toBeDefined(); // 기준 시각이 오늘이 아니면 날짜 (T5.4)
    expect(screen.getByText(/횡단보도 45곳 통제 중, 19곳 예정/)).toBeDefined(); // 곳 단위(64곳)
    expect(screen.getByText("마라톤 1구간 세종대로 사거리~숭례문 오거리")).toBeDefined();
    expect(screen.queryByText(/^marathon /)).toBeNull(); // 코드값은 화면에 안 나온다
    expect(screen.getAllByText(/뒤 해제/).length).toBeGreaterThan(0); // confirmed 행 배지
    expect(screen.getAllByText("제한").length).toBeGreaterThan(0); // scheduled 행 배지
    expect(screen.getByLabelText("기준 시각")).toBeDefined();
    expect(screen.getByText("07:45")).toBeDefined();
    // T5.9 — 사건 전체 수, 출처 줄 없음, 목록 위 기준 시각(실시간 돌발 없으면 회색 경고)
    expect(screen.getByText("07:23–08:57 · 횡단보도 58곳")).toBeDefined(); // 2구간, 기록 창 그대로
    expect(screen.queryByText(/확신/)).toBeNull();
    expect(screen.queryByText(/시각표·|시각표 ·/)).toBeNull();
    expect(screen.getByText("경찰청 11/6 공지 · 마라톤 3/12 시각표 기준")).toBeDefined();
    expect(screen.getByText("실시간 돌발(TOPIS)은 아직 받지 않아요")).toBeDefined();
  });

  it("11/7 15:00 — 공지 행은 파서 제목·둘째 줄, 원문은 '공지 원문 보기'에서만 (T5.9)", () => {
    render(
      <Providers at={T1107} closures={fc1107}>
        <ClosureSheet />
      </Providers>,
    );
    expect(screen.getByText("시의회~숭례문오거리 집회 → 광화문·고용노동청 행진")).toBeDefined();
    expect(screen.getByText("5만 명 · 태평로")).toBeDefined();
    expect(screen.getByText("15:00–16:00 · 횡단보도 31곳")).toBeDefined();
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
