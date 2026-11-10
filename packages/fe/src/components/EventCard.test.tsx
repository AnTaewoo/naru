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
  it("11/9 13:30 국회대로 지도 행진 — 통제 중·행진, 짧은 제목과 지나는 곳 전부, 해제 예정·출처·확신도·75곳", () => {
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
    expect(screen.getByText("TOPIS 통제지도")).toBeDefined();
    expect(screen.getByText("높음")).toBeDefined();
    expect(screen.getByText("75곳")).toBeDefined();
    // 통제 근거 = TOPIS 통제지도 글(공지 원문) — 누르기 전엔 없다
    const excerpt = /※행진:의사당역→마포대교→공덕역/;
    expect(screen.queryByText(excerpt)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "통제 근거 보기" }));
    expect(screen.getByText(excerpt)).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "카드 닫기" }));
    expect(closed).toBe(1);
    expect(screen.queryByRole("button", { name: "이 구역 피해서 길찾기" })).toBeNull(); // onAvoid 없음
  });

  it("이 구역 피해서 길찾기 (T7.6) — onAvoid 가 있으면 버튼, 누르면 부른다 (11/7 경찰청 r04)", () => {
    let asked = 0;
    render(
      <EventCard
        event={eventById(a.body.events, "2e930ec6deeb")}
        atMs={a.atMs}
        onClose={() => undefined}
        onAvoid={() => (asked += 1)}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "이 구역 피해서 길찾기" }));
    expect(asked).toBe(1);
  });

  it("11/7 15:30 경찰청 r01 — 시작했는데 근거가 없으면 '확인 전', 확신도 높음(0.85)·경찰청 공지", () => {
    render(
      <EventCard
        event={eventById(a.body.events, "be5f89a4ebf3")}
        atMs={a.atMs}
        onClose={() => undefined}
      />,
    );
    expect(screen.getByText("확인 전")).toBeDefined();
    expect(screen.getByText("12:00 시작 · 확인 전")).toBeDefined();
    expect(screen.getByText("경찰청 공지")).toBeDefined();
    expect(screen.getByText("5만 명 · 세종대로")).toBeDefined();
  });

  it("3/15 07:45 마라톤 10구간 — 공지가 없으면 근거 버튼이 없다, 1시간 27분 뒤 시작·마라톤 시간표", () => {
    render(
      <EventCard
        event={eventById(m.body.events, "e1d0e06932a8")}
        atMs={m.atMs}
        onClose={() => undefined}
      />,
    );
    expect(screen.getByText("1시간 27분 뒤 시작")).toBeDefined();
    expect(screen.getByText("마라톤 시간표")).toBeDefined();
    expect(screen.getByText("8곳")).toBeDefined();
    expect(screen.queryByRole("button", { name: "통제 근거 보기" })).toBeNull();
  });
});
