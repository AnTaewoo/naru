// /licenses 데이터 기준 시각 (T7.13) — 렌더 테스트. 사건 응답 기록의 data_as_of 를 Provider 초기 state 로 넣는다
// (네트워크 없음, CONVENTIONS §5.7-2). 기대값은 기록을 열어 확인한 게시·수신 시각
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createNaruApiClient } from "../api/naruApiClient";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider, type ClosureState } from "../state/ClosureProvider";
import { TimeProvider } from "../state/TimeProvider";
import { recordedEvents } from "../test/recorded";
import { DataAsOf } from "./DataAsOf";

function renderWith(dataAsOf: ClosureState["dataAsOf"]) {
  render(
    <ApiProvider client={createNaruApiClient("/api")}>
      <TimeProvider initialT="2026-11-07T15:30:00+09:00">
        <ClosureProvider fetchEnabled={false} initialState={{ dataAsOf }}>
          <DataAsOf />
        </ClosureProvider>
      </TimeProvider>
    </ApiProvider>,
  );
}

describe("DataAsOf (T7.13)", () => {
  it("예전 시트 문구 그대로 — 개발 DB 기록: 경찰청 11/6 공지 · 마라톤 3/12 시각표, 실시간 돌발이 없으면 회색 줄", () => {
    renderWith(recordedEvents().data_as_of);
    expect(screen.getByText("경찰청 11/6 공지 · 마라톤 3/12 시각표 기준")).toBeDefined();
    expect(screen.getByText("실시간 돌발(TOPIS)은 아직 받지 않아요")).toBeDefined();
  });

  it("운영 기록 — TOPIS 19:24(돌발 수신) · 경찰청 11/6 공지 · 마라톤 3/12 시각표", () => {
    renderWith(recordedEvents("closure_events_prod_1107_1530").data_as_of);
    expect(
      screen.getByText("TOPIS 19:24 · 경찰청 11/6 공지 · 마라톤 3/12 시각표 기준"),
    ).toBeDefined();
  });

  it("사건 응답 전이면 불러오는 중", () => {
    renderWith(null);
    expect(screen.getByText("불러오는 중…")).toBeDefined();
  });
});
