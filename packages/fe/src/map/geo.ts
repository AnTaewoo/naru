// 표시용 거리 (T7.14) — 검색 결과마다 지도 가운데부터 "387m". 화면 글자에만 쓴다(경로·통제 판단은 BE 가 —
// 공간 연산은 Python, CLAUDE.md §3-5). 하버사인, 지구 평균 반지름
import type { LngLat } from "./layers/routeLayer";

const EARTH_R_M = 6_371_008.8;

/** 두 점([lng, lat]) 사이 거리(m) */
export function distanceM(a: LngLat, b: LngLat): number {
  const rad = Math.PI / 180;
  const p1 = a[1] * rad;
  const p2 = b[1] * rad;
  const dp = p2 - p1;
  const dl = (b[0] - a[0]) * rad;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * EARTH_R_M * Math.asin(Math.sqrt(h));
}

/** 지도 bbox("w,s,e,n") 가운데 [lng, lat] — 형식이 틀리면 null */
export function bboxCenter(bbox: string): LngLat | null {
  const nums = bbox.split(",").map(Number);
  const [w, s, e, n] = nums;
  if (nums.length !== 4 || !nums.every(Number.isFinite)) return null;
  if (w === undefined || s === undefined || e === undefined || n === undefined) return null;
  return [(w + e) / 2, (s + n) / 2];
}
