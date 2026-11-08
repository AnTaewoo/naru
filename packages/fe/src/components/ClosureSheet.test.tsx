// 렌더 테스트 — Provider 초기 state 에 recorded 응답을 넣고 그린다. 네트워크 없음 (CONVENTIONS §5.7-2)
import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { createNaruApiClient } from "../api/naruApiClient";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider, useClosureDispatch, useClosures } from "../state/ClosureProvider";
import { TimeProvider } from "../state/TimeProvider";
import { recordedClosures } from "../test/recorded";
import { ClosureSheet, closureRows } from "./ClosureSheet";
import { timelineBars } from "./ClosureTimeline";
import { TimeSlider } from "./TimeSlider";

const T = "2026-03-15T07:45:00+09:00";
const fc0745 = recordedClosures("closures_0745");
const fc0430 = recordedClosures("closures_0430");

function Providers({ children, at = T }: { children: ReactNode; at?: string }) {
  return (
    <ApiProvider client={createNaruApiClient("/api")}>
      <TimeProvider initialT={at}>
        <ClosureProvider
          fetchEnabled={false}
          initialState={{ status: "ready", closures: fc0745, at }}
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
    expect(seg1?.evidence).toEqual(["timetable"]);
    const bars = timelineBars(fc0745, "2026-03-15T00:00:00+09:00");
    expect(bars).toHaveLength(rows.length);
    const seg1bar = bars.find((b) => b.reason.includes("1구간"));
    expect(seg1bar?.leftPct).toBeCloseTo(((7 * 60 + 20) / (24 * 60)) * 100, 3);
    expect(seg1bar?.widthPct).toBeCloseTo((48 / (24 * 60)) * 100, 3);
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
