// 테스트 입력 — data/recorded/naru_api (scripts/record_naru_api.py 가 실제 Flask 에서 받은 응답)
import { readFileSync } from "node:fs";
import path from "node:path";
import type { FeatureCollection, RouteResponse } from "../types/contracts";

export const RECORDED_DIR = path.resolve(__dirname, "../../../../data/recorded/naru_api");

interface Recorded {
  method: string;
  path: string;
  status: number;
  body: unknown;
}

export function recorded(name: string): Recorded {
  return JSON.parse(readFileSync(path.join(RECORDED_DIR, `${name}.json`), "utf-8")) as Recorded;
}

export function recordedClosures(name: string): FeatureCollection {
  return recorded(name).body as FeatureCollection;
}

export function recordedRoute(name: string): RouteResponse {
  return recorded(name).body as RouteResponse;
}
