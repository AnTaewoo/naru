// TimeSlider 재렌더 격리 (CONVENTIONS §5.5) — Provider 를 나눈 까닭. ClosureSheet.test 에서 옮김 (T7.5)
import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { createNaruApiClient } from "../api/naruApiClient";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider, useClosureDispatch, useClosures } from "../state/ClosureProvider";
import { TimeProvider } from "../state/TimeProvider";
import { recordedClosures } from "../test/recorded";
import { TimeSlider } from "./TimeSlider";

const T = "2026-03-15T07:45:00+09:00";
const fc0745 = recordedClosures("closures_0745");
const fc0430 = recordedClosures("closures_0430");

function Providers({ children }: { children: ReactNode }) {
  return (
    <ApiProvider client={createNaruApiClient("/api")}>
      <TimeProvider initialT={T}>
        <ClosureProvider
          fetchEnabled={false}
          initialState={{ status: "ready", closures: fc0745, at: T }}
        >
          {children}
        </ClosureProvider>
      </TimeProvider>
    </ApiProvider>
  );
}

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
