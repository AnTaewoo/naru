// 통제 제보 카드 (T7.15) — 렌더. 횡단보도는 기록 응답(report_nearest_kyobo — naru_test 의 실제 앱), 네트워크 없음
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";
import { createNaruApiClient, parseNearestCrosswalk } from "../api/naruApiClient";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider } from "../state/ClosureProvider";
import { crosswalkOf, reportReducer, type ReportEvent, type ReportState } from "../state/report";
import { RouteProvider, useRoute } from "../state/RouteProvider";
import { TimeProvider } from "../state/TimeProvider";
import { recorded } from "../test/recorded";
import { ReportCard } from "./ReportCard";

const KYOBO: [number, number] = [126.9779039768265, 37.5709686446227]; // 기록 질의 그대로
const kyoboCw = crosswalkOf(parseNearestCrosswalk(recorded("report_nearest_kyobo").body));

function after(...events: ReportEvent[]): ReportState | null {
  return events.reduce<ReportState | null>(reportReducer, null);
}

const READY: ReportEvent[] = [
  { type: "start", field: false },
  { type: "located", point: KYOBO, accuracyM: 14 },
  { type: "found", crosswalk: kyoboCw },
];

function Providers({ report, children }: { report: ReportState | null; children: ReactNode }) {
  return (
    <ApiProvider client={createNaruApiClient("/api")}>
      <TimeProvider initialT="2026-11-10T18:00:00+09:00">
        <ClosureProvider fetchEnabled={false}>
          <RouteProvider fetchEnabled={false} initialState={{ report }}>
            {children}
          </RouteProvider>
        </ClosureProvider>
      </TimeProvider>
    </ApiProvider>
  );
}

function Probe() {
  const { report } = useRoute();
  return (
    <output aria-label="제보 상태">
      {report ? `${report.phase} ${report.sent ?? "-"}` : "없음"}
    </output>
  );
}

describe("ReportCard (T7.15)", () => {
  it("이 횡단보도가 맞나요? 교보생명·종로구·71 m·정확도 ±14 m — 막혔어요를 누르면 보내는 중", () => {
    render(
      <Providers report={after(...READY)}>
        <ReportCard />
        <Probe />
      </Providers>,
    );
    const card = screen.getByRole("article", { name: "통제 제보" });
    expect(card.textContent).toContain("이 횡단보도가 맞나요?");
    expect(card.textContent).toContain("교보생명");
    expect(card.textContent).toContain("종로구");
    expect(card.textContent).toContain("여기서 71 m · 위치 정확도 ±14 m");
    expect(card.textContent).toContain("아직 길찾기에는 쓰지 않아요");
    expect(card.textContent).not.toContain("현장 검증");
    fireEvent.click(screen.getByRole("button", { name: "막혔어요" }));
    expect(screen.getByLabelText("제보 상태").textContent).toBe("sending blocked");
    expect(screen.getByRole("button", { name: "막혔어요" })).toHaveProperty("disabled", true);
  });

  it("현장 검증(?mode=field)이면 배지, 보낸 뒤 고마워요", () => {
    const field = after(
      { type: "start", field: true },
      ...READY.slice(1),
      { type: "send", value: "open" },
      { type: "sent" },
    );
    render(
      <Providers report={field}>
        <ReportCard />
      </Providers>,
    );
    const card = screen.getByRole("article", { name: "통제 제보" });
    expect(card.textContent).toContain("현장 검증");
    expect(screen.getByRole("status").textContent).toContain("열렸다고 제보했어요");
  });

  it("같은 횡단보도 다시(429) → 조금 뒤에, 닫기 → 카드 없음", () => {
    const tooMany = after(
      ...READY,
      { type: "send", value: "blocked" },
      { type: "fail", failure: "too_many" },
    );
    render(
      <Providers report={tooMany}>
        <ReportCard />
        <Probe />
      </Providers>,
    );
    expect(screen.getByRole("alert").textContent).toContain("조금 뒤에 다시");
    expect(screen.queryByRole("button", { name: "다시 하기" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "제보 닫기" }));
    expect(screen.getByLabelText("제보 상태").textContent).toBe("없음");
    expect(screen.queryByRole("article", { name: "통제 제보" })).toBeNull();
  });

  it("위치 찾는 중 → 횡단보도 찾는 중, 위치 권한이 꺼져 있으면 다시 하기", () => {
    const { unmount } = render(
      <Providers report={after({ type: "start", field: false })}>
        <ReportCard />
      </Providers>,
    );
    expect(screen.getByRole("article", { name: "통제 제보" }).textContent).toContain(
      "지금 위치를 찾고 있어요",
    );
    unmount();
    render(
      <Providers
        report={after({ type: "start", field: false }, { type: "fail", failure: "denied" })}
      >
        <ReportCard />
      </Providers>,
    );
    expect(screen.getByRole("alert").textContent).toContain("위치 권한이 꺼져 있어");
    expect(screen.getByRole("button", { name: "다시 하기" })).toBeDefined();
  });
});
