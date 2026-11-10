"use client";

import { useCallback, useEffect, useState } from "react";
import { isIOS, pushSupport, type PushEnv, type PushState } from "./support";

// 알림 훅 (ADR-014 D — Provider 추가 없음, T7.7) — 마운트 뒤 브라우저 지원을 읽고 서비스워커(/sw.js)를 등록한다.
// 권한은 enable()(버튼) 에서만 묻는다. 구독(PushManager.subscribe)은 T7.8 VAPID 키 뒤
export const SW_URL = "/sw.js";

function readEnv(): PushEnv {
  const nav = window.navigator;
  const ios = isIOS(nav.userAgent, nav.platform, nav.maxTouchPoints);
  // jsdom(렌더 테스트)엔 matchMedia 가 없다
  const standalone =
    (nav as Navigator & { standalone?: boolean }).standalone === true ||
    (typeof window.matchMedia === "function" &&
      window.matchMedia("(display-mode: standalone)").matches);
  return {
    serviceWorker: "serviceWorker" in nav,
    pushManager: "PushManager" in window,
    notification: "Notification" in window,
    permission: "Notification" in window ? Notification.permission : null,
    ios,
    standalone,
  };
}

export function usePush(): { state: PushState; enable: () => void } {
  const [state, setState] = useState<PushState>("unknown");
  useEffect(() => {
    const env = readEnv();
    setState(pushSupport(env));
    if (!env.serviceWorker) return;
    navigator.serviceWorker.register(SW_URL, { scope: "/" }).catch(() => setState("unsupported"));
  }, []);
  const enable = useCallback(() => {
    if (!("Notification" in window)) return;
    void Notification.requestPermission().then((permission) =>
      setState(pushSupport({ ...readEnv(), permission })),
    );
  }, []);
  return { state, enable };
}
