// 알림(B) 지원 판정 — 순수 함수 (ADR-014 D: Provider 없이 훅, T7.7). 브라우저 값은 usePush 가 읽어 넘긴다.
export type PushState =
  | "unknown" // 서버 렌더·마운트 전
  | "unsupported" // 서비스워커·Push·Notification 중 하나가 없다
  | "ios_install" // iPhone·iPad Safari 브라우저 탭 — 홈 화면에 추가해야 알림(iOS 16.4+)
  | "denied"
  | "default"
  | "granted";

export interface PushEnv {
  serviceWorker: boolean;
  pushManager: boolean;
  notification: boolean;
  permission: NotificationPermission | null;
  ios: boolean;
  standalone: boolean;
}

/** iPhone·iPad — iPadOS 13+ 는 Mac 처럼 보이지만 터치가 있다 */
export function isIOS(userAgent: string, platform: string, maxTouchPoints: number): boolean {
  return /iPhone|iPad|iPod/.test(userAgent) || (platform === "MacIntel" && maxTouchPoints > 1);
}

export function pushSupport(env: PushEnv): PushState {
  if (!env.serviceWorker || !env.pushManager || !env.notification || env.permission === null) {
    return env.ios && !env.standalone ? "ios_install" : "unsupported";
  }
  if (env.permission === "denied") return "denied";
  if (env.permission === "granted") return "granted";
  return env.ios && !env.standalone ? "ios_install" : "default";
}
