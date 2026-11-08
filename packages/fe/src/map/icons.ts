// 지도 아이콘 — 글리프(폰트) 서버 없이 캔버스로 그린다. × 확인 · ! 예정 · 빗금 예정 구역 (목업 01_home 범례)
import { COLORS } from "./colors";

export const ICON_IDS = { x: "naru-x", bang: "naru-bang", hatch: "naru-hatch" } as const;
export type IconId = (typeof ICON_IDS)[keyof typeof ICON_IDS];

/** 레티나 대응 — 아이콘은 2배 크기로 그리고 pixelRatio 2 로 등록한다 */
export const ICON_PIXEL_RATIO = 2;
export const ICON_SIZE = 24 * ICON_PIXEL_RATIO;
export const HATCH_SIZE = 8 * ICON_PIXEL_RATIO;

type Draw = (ctx: CanvasRenderingContext2D, size: number) => void;

/** 흰 × (빨간 점 위에 얹는다) */
export const drawX: Draw = (ctx, size) => {
  const m = size * 0.3;
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = size * 0.13;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(m, m);
  ctx.lineTo(size - m, size - m);
  ctx.moveTo(size - m, m);
  ctx.lineTo(m, size - m);
  ctx.stroke();
};

/** 흰 ! (노란 점 위에 얹는다) */
export const drawBang: Draw = (ctx, size) => {
  const cx = size / 2;
  ctx.strokeStyle = "#ffffff";
  ctx.fillStyle = "#ffffff";
  ctx.lineWidth = size * 0.13;
  ctx.lineCap = "round";
  ctx.beginPath();
  ctx.moveTo(cx, size * 0.24);
  ctx.lineTo(cx, size * 0.58);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(cx, size * 0.76, size * 0.075, 0, Math.PI * 2);
  ctx.fill();
};

/** 보라 빗금 패턴 (fill-pattern 용, 반복 타일) */
export const drawHatch: Draw = (ctx, size) => {
  ctx.fillStyle = "rgba(122, 92, 240, 0.10)";
  ctx.fillRect(0, 0, size, size);
  ctx.strokeStyle = COLORS.zone;
  ctx.globalAlpha = 0.55;
  ctx.lineWidth = size * 0.12;
  ctx.beginPath();
  // 타일 경계에서 이어지도록 대각선 세 개
  for (const off of [-size, 0, size]) {
    ctx.moveTo(off, size);
    ctx.lineTo(off + size, 0);
  }
  ctx.stroke();
  ctx.globalAlpha = 1;
};

export const ICON_DRAWS: Record<IconId, { draw: Draw; size: number }> = {
  [ICON_IDS.x]: { draw: drawX, size: ICON_SIZE },
  [ICON_IDS.bang]: { draw: drawBang, size: ICON_SIZE },
  [ICON_IDS.hatch]: { draw: drawHatch, size: HATCH_SIZE },
};

/** 브라우저에서만 — 캔버스에 그려 ImageData 로. 2D 컨텍스트가 없으면 null */
export function renderIcon(id: IconId): ImageData | null {
  const { draw, size } = ICON_DRAWS[id];
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  draw(ctx, size);
  return ctx.getImageData(0, 0, size, size);
}
