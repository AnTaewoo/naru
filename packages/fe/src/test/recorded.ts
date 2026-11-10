// 테스트 입력 — data/recorded/naru_api (scripts/record_naru_api.py 가 실제 Flask 에서 받은 응답)
import { readFileSync } from "node:fs";
import path from "node:path";
import type {
  ClosureEvent,
  ClosureEventsResponse,
  FeatureCollection,
  RouteResponse,
} from "../types/contracts";

export const RECORDED_DIR = path.resolve(__dirname, "../../../../data/recorded/naru_api");

interface Recorded {
  method: string;
  path: string;
  /** 기록할 때 보낸 질의 (예: route 의 from·to·depart_at) */
  query?: Record<string, string>;
  /** 기록할 때 POST 로 보낸 본문 (통제 제보 T7.15 — 기기 토큰은 빼고 남겼다) */
  json?: unknown;
  status: number;
  /** 응답 ETag (사건 v2 기록, scripts/record_live_events.py) */
  etag?: string;
  /** 받은 시각 (운영 기록, scripts/record_prod_events.py) */
  fetched_at?: string;
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

/** GET /closures/events (T5.4) — 기록할 때 개발 DB 에 있던 통제 사건 전부 */
export function recordedEvents(name = "closure_events"): ClosureEventsResponse {
  return recorded(name).body as ClosureEventsResponse;
}

/** 사건 v2 기록 (scripts/record_live_events.py, T7.4) — 응답과 그 기준 시각(ms) */
export function recordedLive(name: string): { body: ClosureEventsResponse; atMs: number } {
  const body = recordedEvents(name);
  return { body, atMs: Date.parse(body.at) };
}

/** 기록 사건 하나 — 없으면 테스트가 실패한다 */
export function eventById(events: readonly ClosureEvent[], id: string): ClosureEvent {
  const e = events.find((x) => x.id === id);
  if (!e) throw new Error(`기록에 사건 ${id} 가 없다`);
  return e;
}

const RECORDED_ROOT = path.dirname(RECORDED_DIR);

/** AI 후보 하나 — candidates/<출처>/<파일>.json (워커가 BE 로 보낸 배치 그대로, T7.14 확신도 문구 입력) */
export interface RecordedCandidate {
  candidate_id: string;
  confidence: number;
  impact: string;
  status_hint: string;
  type: string;
}

export function recordedCandidate(file: string, candidateId: string): RecordedCandidate {
  const raw = readFileSync(path.join(RECORDED_ROOT, "candidates", `${file}.json`), "utf-8");
  const batch = JSON.parse(raw) as { candidates: RecordedCandidate[] };
  const found = batch.candidates.find((c) => c.candidate_id === candidateId);
  if (!found) throw new Error(`후보 없음: ${file} ${candidateId}`);
  return found;
}

/** 공지 파서 응답(llm/anthropic/claude-haiku-5-5@api/notice_v2/<이름>.json)의 항목 — 후보가 되기 전 값 */
export interface RecordedNoticeItem {
  confidence: number;
  impact: string;
  kind: string;
  points: { name: string }[];
}

export function recordedNoticeItems(name: string): RecordedNoticeItem[] {
  const file = path.join(
    RECORDED_ROOT,
    "llm",
    "anthropic",
    "claude-haiku-5-5@api",
    "notice_v2",
    `${name}.json`,
  );
  const doc = JSON.parse(readFileSync(file, "utf-8")) as {
    response: { content: { type: string; input?: { items: RecordedNoticeItem[] } }[] };
  };
  const tool = doc.response.content.find((b) => b.type === "tool_use");
  if (!tool?.input) throw new Error(`tool_use 없음: ${name}`);
  return tool.input.items;
}
