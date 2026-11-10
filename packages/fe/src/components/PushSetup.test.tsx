// 통제 알림 칸 (T7.7 → T7.10) — 상태별 렌더. 관심 지역은 기록 watch_areas(실제 앱 응답), 브라우저 API 는 안 건드린다
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { initialStore, type PushStore } from "../push/store";
import { recorded } from "../test/recorded";
import type { WatchAreasResponse } from "../types/contracts";
import { PushSetupView } from "./PushSetup";

const { areas } = recorded("watch_areas").body as WatchAreasResponse;
const none = () => undefined;

function view(
  store: Partial<PushStore>,
  handlers: Partial<Parameters<typeof PushSetupView>[0]> = {},
) {
  return render(
    <PushSetupView
      store={{ ...initialStore, ...store }}
      onEnable={handlers.onEnable ?? none}
      onDisable={handlers.onDisable ?? none}
      onUnwatch={handlers.onUnwatch ?? none}
    />,
  );
}

describe("PushSetupView (T7.10)", () => {
  it("default — 이유 한 줄과 '통제 알림 받기' 버튼, 누르면 onEnable; 켜는 중엔 비활성", () => {
    let asked = 0;
    const { rerender } = view({ support: "default" }, { onEnable: () => (asked += 1) });
    const box = screen.getByRole("region", { name: "통제 알림" });
    expect(box.textContent).toContain("관심 지역 근처에 통제가 생기면");
    fireEvent.click(screen.getByRole("button", { name: "통제 알림 받기" }));
    expect(asked).toBe(1);
    rerender(
      <PushSetupView
        store={{ ...initialStore, support: "default", busy: true }}
        onEnable={none}
        onDisable={none}
        onUnwatch={none}
      />,
    );
    expect(screen.getByRole("button", { name: "알림을 켜는 중…" })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("구독되면 '알림 받는 중' + 관심 지역 목록(라벨·반경, 마지막 위치)·빼기·알림 끄기·개인정보 한 줄", () => {
    const removed: number[] = [];
    let off = 0;
    const saved = areas.find((a) => a.kind === "saved");
    view(
      {
        support: "granted",
        endpoint: "https://push.example/abc",
        areas,
        labels: { [String(saved?.id)]: "동화면세점 앞 → 종로1가사거리 → 동화면세점 앞 행진" },
      },
      { onUnwatch: (id) => removed.push(id), onDisable: () => (off += 1) },
    );
    const box = screen.getByRole("region", { name: "통제 알림" });
    expect(box.textContent).toContain("알림 받는 중");
    const items = screen.getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual([
      expect.stringContaining("동화면세점 앞 → 종로1가사거리 → 동화면세점 앞 행진 · 500 m"),
      expect.stringContaining("마지막 위치 근처 · 500 m"),
    ]);
    fireEvent.click(screen.getAllByRole("button", { name: /^빼기:/ })[0] as HTMLElement);
    expect(removed).toEqual([saved?.id]);
    fireEvent.click(screen.getByRole("button", { name: "알림 끄기" }));
    expect(off).toBe(1);
    expect(box.textContent).toContain("150 m 단위로 3시간만");
    expect(screen.getByRole("link", { name: "보기" }).getAttribute("href")).toBe("/licenses#push");
  });

  it("구독됐는데 관심 지역이 없으면 ☆ 안내, 실패는 alert, denied·ios_install·unsupported 는 안내만, unknown 은 없음", () => {
    const { rerender } = view({
      support: "granted",
      endpoint: "https://push.example/abc",
      areas: [],
    });
    expect(screen.getByText(/아직 관심 지역이 없어요/)).toBeDefined();
    rerender(
      <PushSetupView
        store={{ ...initialStore, support: "granted", error: "failed" }}
        onEnable={none}
        onDisable={none}
        onUnwatch={none}
      />,
    );
    expect(screen.getByRole("alert").textContent).toContain("구독을 만들지 못했어요");
    for (const [support, text] of [
      ["ios_install", /홈 화면에 추가/],
      ["denied", /브라우저 설정/],
      ["unsupported", /지원하지 않아요/],
    ] as const) {
      rerender(
        <PushSetupView
          store={{ ...initialStore, support }}
          onEnable={none}
          onDisable={none}
          onUnwatch={none}
        />,
      );
      expect(screen.getByText(text)).toBeDefined();
    }
    rerender(
      <PushSetupView store={initialStore} onEnable={none} onDisable={none} onUnwatch={none} />,
    );
    expect(screen.queryByRole("region", { name: "통제 알림" })).toBeNull();
  });
});
