// 알림 지원 판정 (T7.7) — 순수 함수. UA 는 Playwright devices 의 실제 문자열(iPhone 13·Desktop Chrome)
import { devices } from "@playwright/test";
import { describe, expect, it } from "vitest";
import { isIOS, pushSupport, type PushEnv } from "./support";

const iphone = devices["iPhone 13"]?.userAgent ?? "";
const chrome = devices["Desktop Chrome"]?.userAgent ?? "";
const full: PushEnv = {
  serviceWorker: true,
  pushManager: true,
  notification: true,
  permission: "default",
  ios: false,
  standalone: false,
};

describe("pushSupport (T7.7)", () => {
  it("iPhone·iPad 판정 — UA, 또는 Mac 처럼 보이는 iPadOS(터치 있음)", () => {
    expect(iphone).toContain("iPhone");
    expect(isIOS(iphone, "iPhone", 5)).toBe(true);
    expect(isIOS(chrome, "Linux x86_64", 0)).toBe(false);
    expect(isIOS(chrome.replace("Linux x86_64", "Macintosh"), "MacIntel", 5)).toBe(true);
    expect(isIOS("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "MacIntel", 0)).toBe(false);
  });

  it("권한대로 — default 는 버튼, granted·denied 는 그대로", () => {
    expect(pushSupport(full)).toBe("default");
    expect(pushSupport({ ...full, permission: "granted" })).toBe("granted");
    expect(pushSupport({ ...full, permission: "denied" })).toBe("denied");
  });

  it("iPhone 브라우저 탭은 홈 화면 안내 — Notification 이 없어도, 있어도(default). 홈 화면(standalone)은 보통", () => {
    expect(pushSupport({ ...full, ios: true, notification: false, permission: null })).toBe(
      "ios_install",
    );
    expect(pushSupport({ ...full, ios: true })).toBe("ios_install");
    expect(pushSupport({ ...full, ios: true, standalone: true })).toBe("default");
    expect(pushSupport({ ...full, ios: true, standalone: true, permission: "granted" })).toBe(
      "granted",
    );
  });

  it("서비스워커·Push·Notification 중 하나라도 없으면(iPhone 아님) 지원 안 함", () => {
    expect(pushSupport({ ...full, serviceWorker: false })).toBe("unsupported");
    expect(pushSupport({ ...full, pushManager: false })).toBe("unsupported");
    expect(pushSupport({ ...full, notification: false, permission: null })).toBe("unsupported");
  });
});
