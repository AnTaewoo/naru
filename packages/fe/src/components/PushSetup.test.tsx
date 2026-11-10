// 알림 켜기 칸 (T7.7) — 상태별 렌더. 브라우저 API 는 안 건드린다(PushSetupView 에 상태를 넣는다)
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PushSetupView } from "./PushSetup";

describe("PushSetupView (T7.7)", () => {
  it("default — 이유 한 줄과 '통제 알림 받기' 버튼, 누르면 onEnable", () => {
    let asked = 0;
    render(<PushSetupView state="default" onEnable={() => (asked += 1)} />);
    const box = screen.getByRole("region", { name: "통제 알림" });
    expect(box.textContent).toContain("관심 지역 근처에 통제가 생기면");
    fireEvent.click(screen.getByRole("button", { name: "통제 알림 받기" }));
    expect(asked).toBe(1);
  });

  it("granted 는 허용됐다는 줄(관심 지역은 다음 업데이트), denied·ios_install·unsupported 는 안내만, unknown 은 없음", () => {
    const { rerender } = render(<PushSetupView state="granted" onEnable={() => undefined} />);
    expect(screen.getByRole("status").textContent).toContain("다음 업데이트");
    expect(screen.queryByRole("button")).toBeNull();
    rerender(<PushSetupView state="ios_install" onEnable={() => undefined} />);
    expect(screen.getByText(/홈 화면에 추가/)).toBeDefined();
    rerender(<PushSetupView state="denied" onEnable={() => undefined} />);
    expect(screen.getByText(/브라우저 설정/)).toBeDefined();
    rerender(<PushSetupView state="unsupported" onEnable={() => undefined} />);
    expect(screen.getByText(/지원하지 않아요/)).toBeDefined();
    rerender(<PushSetupView state="unknown" onEnable={() => undefined} />);
    expect(screen.queryByRole("region", { name: "통제 알림" })).toBeNull();
  });
});
