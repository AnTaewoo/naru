// 통제 근거 (T7.15) — 사유별 "최근 1시간 제보 N건". 경로·통제는 기록(route_0745·closures_0745), 제보 집계는
// 기록 reports_recent(naru_test 실제 앱 — 교보생명·세종대로사거리 06-0000023206 각 막힘 1)
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { createNaruApiClient, parseRecentReports } from "../api/naruApiClient";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider } from "../state/ClosureProvider";
import { RouteProvider } from "../state/RouteProvider";
import { TimeProvider } from "../state/TimeProvider";
import { recorded, recordedClosures, recordedRoute } from "../test/recorded";
import { EvidencePopover, evidenceGroups } from "./EvidencePopover";

const route = recordedRoute("route_0745");
const closures = recordedClosures("closures_0745");
const counts = parseRecentReports(recorded("reports_recent").body).counts;

describe("EvidencePopover 제보 수 (T7.15)", () => {
  it("사유마다 그 사유 횡단보도의 제보를 더한다 — 1구간(세종대로사거리) 1건, 출발지 0건", () => {
    const groups = evidenceGroups(route.avoided, closures, counts);
    const leg1 = groups.find((g) => g.reason.includes("1구간"));
    const start = groups.find((g) => g.reason.includes("출발지"));
    expect(leg1?.reports).toEqual({ blocked: 1, open: 0 });
    expect(start?.reports).toEqual({ blocked: 0, open: 0 });
    expect(evidenceGroups(route.avoided, closures, null).every((g) => g.reports === null)).toBe(
      true,
    );
  });

  it("화면 — 1구간 카드에만 '최근 1시간 제보 1건 (막힘 1 · 열림 0)'", () => {
    render(
      <ApiProvider client={createNaruApiClient("/api")}>
        <TimeProvider initialT="2026-03-15T07:45:00+09:00">
          <ClosureProvider fetchEnabled={false} initialState={{ closures }}>
            <RouteProvider fetchEnabled={false} initialState={{ route, reportCounts: counts }}>
              <EvidencePopover route={route} />
            </RouteProvider>
          </ClosureProvider>
        </TimeProvider>
      </ApiProvider>,
    );
    const lines = screen.getAllByText(/최근 1시간 제보/);
    expect(lines.map((x) => x.textContent)).toEqual(["최근 1시간 제보 1건 (막힘 1 · 열림 0)"]);
  });
});
