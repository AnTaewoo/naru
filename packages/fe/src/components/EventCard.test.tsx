// 사건 카드 (T7.5, 목업 03_closure) — 렌더 테스트. 입력은 사건 v2 기록(scripts/record_live_events.py), 네트워크 없음.
// 기대값은 기록을 열어 확인한 창·출처·확신도·횡단보도 수
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { eventById, recordedLive } from "../test/recorded";
import { EventCard } from "./EventCard";

const n = recordedLive("closure_events_live_1109_1330");
const a = recordedLive("closure_events_live_1107_1530");
const m = recordedLive("closure_events_live_0315_0745");

describe("EventCard", () => {
  it("11/9 13:30 국회대로 지도 행진 — 통제 중·행진, 짧은 제목과 지나는 곳 전부, 날짜·창·해제 예정", () => {
    let closed = 0;
    render(
      <EventCard
        event={eventById(n.body.events, "ccaa9980c6ac")}
        atMs={n.atMs}
        onClose={() => (closed += 1)}
      />,
    );
    const card = screen.getByRole("article", { name: "국회의사당앞 → 효자동삼거리 행진" });
    expect(card.textContent).toContain("통제 중");
    expect(card.textContent).toContain("행진");
    expect(screen.getByText(/^국회의사당앞 → 서강대교남단 → .* → 효자동삼거리$/)).toBeDefined();
    expect(screen.getByText("11월 9일 (월)")).toBeDefined();
    expect(screen.getByText("11:00–15:30")).toBeDefined();
    expect(screen.getByText("15:30 해제 예정")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "카드 닫기" }));
    expect(closed).toBe(1);
  });

  it("11/7 15:30 경찰청 r01 — 시작했는데 근거가 없으면 '확인 전'", () => {
    render(
      <EventCard
        event={eventById(a.body.events, "be5f89a4ebf3")}
        atMs={a.atMs}
        onClose={() => undefined}
      />,
    );
    expect(screen.getByText("확인 전")).toBeDefined();
    expect(screen.getByText("12:00 시작 · 확인 전")).toBeDefined();
    expect(screen.getByText("5만 명 · 세종대로")).toBeDefined();
  });

  it("3/15 07:45 마라톤 10구간 — 1시간 27분 뒤 시작", () => {
    render(
      <EventCard
        event={eventById(m.body.events, "e1d0e06932a8")}
        atMs={m.atMs}
        onClose={() => undefined}
      />,
    );
    expect(screen.getByText("1시간 27분 뒤 시작")).toBeDefined();
  });
});
