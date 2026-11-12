// 하단 시트 (T5.6) — 순수(단계 높이·가까운 단계) + 렌더(손잡이 탭). 드래그는 jsdom 에 레이아웃이 없어
// e2e(e2e/sheet.spec.ts, 실제 Chrome)에서 본다. 높이 기준 664 px = Playwright devices["iPhone 13"] 보이는 영역
import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import {
  BottomSheet,
  SHEET_COLLAPSED_PX,
  nearestStage,
  stageHeight,
  type SheetStage,
} from "./BottomSheet";

const IPHONE13_H = 664;

describe("단계 높이·가까운 단계 (순수)", () => {
  it("접힘 96px, 절반 50%, 전체 88% — iPhone 13 이면 96·332·584", () => {
    expect(SHEET_COLLAPSED_PX).toBe(96);
    expect(stageHeight("collapsed", IPHONE13_H)).toBe(96);
    expect(stageHeight("half", IPHONE13_H)).toBe(332);
    expect(stageHeight("full", IPHONE13_H)).toBe(584);
  });

  it("위에 떠 있는 UI 가 있으면 전체 = 화면 − 그 높이 (길찾기 패널 112px → 552, T5.10)", () => {
    expect(stageHeight("full", IPHONE13_H, 112)).toBe(552);
    expect(nearestStage(582, IPHONE13_H, 112)).toBe("full");
    expect(nearestStage(380, IPHONE13_H, 112)).toBe("half");
  });

  it("놓은 높이에서 가장 가까운 단계로", () => {
    expect(nearestStage(150, IPHONE13_H)).toBe("collapsed");
    expect(nearestStage(300, IPHONE13_H)).toBe("half");
    expect(nearestStage(420, IPHONE13_H)).toBe("half");
    expect(nearestStage(500, IPHONE13_H)).toBe("full");
    expect(nearestStage(900, IPHONE13_H)).toBe("full");
  });
});

function Harness({ initial }: { initial: SheetStage }) {
  const [stage, setStage] = useState<SheetStage>(initial);
  return (
    <BottomSheet label="시험 시트" stage={stage} onStage={setStage}>
      <p>내용</p>
    </BottomSheet>
  );
}

describe("BottomSheet 렌더", () => {
  it("손잡이 탭 — 접힘↔절반, 전체에서 누르면 접힘", () => {
    render(<Harness initial="half" />);
    const sheet = screen.getByRole("region", { name: "시험 시트" });
    const grip = screen.getByRole("button", { name: "시트 높이" });
    expect(sheet.dataset.stage).toBe("half");
    expect(grip.getAttribute("aria-expanded")).toBe("true");
    fireEvent.click(grip);
    expect(sheet.dataset.stage).toBe("collapsed");
    expect(grip.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(grip);
    expect(sheet.dataset.stage).toBe("half");
  });

  it("고지 줄 — 펼치면 맨 아래 '오픈소스·데이터 고지' → /licenses, 접힘에선 없다 (T5.12)", () => {
    render(<Harness initial="collapsed" />);
    expect(screen.queryByRole("link", { name: "오픈소스·데이터 고지" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "시트 높이" }));
    const link = screen.getByRole("link", { name: "오픈소스·데이터 고지" });
    expect(link.getAttribute("href")).toBe("/licenses");
  });

  it("전체에서 탭 → 접힘", () => {
    render(<Harness initial="full" />);
    fireEvent.click(screen.getByRole("button", { name: "시트 높이" }));
    expect(screen.getByRole("region", { name: "시험 시트" }).dataset.stage).toBe("collapsed");
  });
});
