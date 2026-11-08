// 상태 색 — 화면 시안 01_home.html 의 CSS 변수에서 옮김 (CONVENTIONS §5.8·§5.9)
import type { Status } from "../types/contracts";

export const COLORS = {
  stop: "#e5322d", // confirmed — 지금 못 건너는 횡단보도 (빨강 X)
  stopBg: "#fdecec",
  slow: "#f5a300", // scheduled — 통제 예정 (노랑 ⚠, 느리게 계산)
  slowBg: "#fff5dc",
  zone: "#7a5cf0", // zone_scheduled — 집회 예정 구역 (보라 빗금, 지도에만)
  zoneBg: "#efeafe",
  blue: "#2d6bff", // 경로·지하보도 입구
  blueBg: "#eaf1ff",
  ok: "#1f9d55", // released — 해제
  okBg: "#e6f6ec",
  gray: "#9a9a9a",
  grayBg: "#f0f0f0",
  ink: "#1e1e1e",
  ink2: "#666666",
  line: "#e6e6e6",
} as const;

export const STATUS_COLOR: Record<Status, string> = {
  confirmed: COLORS.stop,
  scheduled: COLORS.slow,
  released: COLORS.gray,
  zone_scheduled: COLORS.zone,
};

export const STATUS_BG: Record<Status, string> = {
  confirmed: COLORS.stopBg,
  scheduled: COLORS.slowBg,
  released: COLORS.grayBg,
  zone_scheduled: COLORS.zoneBg,
};
