// enum 코드값 → 한국어 라벨. 한국어는 이 파일에만 (INTERFACE §4, CONVENTIONS §5.8)
import type { ClosureType, EvidenceKind, Impact, LegKind, Status } from "../types/contracts";

export const STATUS_KO: Record<Status, string> = {
  scheduled: "예정",
  confirmed: "확인",
  released: "해제",
  zone_scheduled: "예정 구역",
};

/** 목업의 우측 배지 문구 (01_home.html 행): 확인 → "통제 중", 예정 → "제한", 구역 → "예정" */
export const STATUS_BADGE_KO: Record<Status, string> = {
  confirmed: "통제 중",
  scheduled: "제한",
  released: "해제",
  zone_scheduled: "예정",
};

export const TYPE_KO: Record<ClosureType, string> = {
  marathon: "마라톤",
  march: "행진",
  rally: "집회",
  event: "행사",
  incident: "돌발",
};

/**
 * BE 의 reason 은 자유 문장이다. 코스·시각표 후보는 "marathon 1구간 …" 처럼 type 코드값으로 시작하므로
 * 화면에선 그 앞머리만 한국어로 바꾼다 (BE 는 한국어 라벨을 넣지 않는다 — CONVENTIONS §4.5)
 */
export function reasonKo(reason: string): string {
  const space = reason.indexOf(" ");
  const head = space < 0 ? reason : reason.slice(0, space);
  if (head in TYPE_KO) return TYPE_KO[head as ClosureType] + reason.slice(head.length);
  return reason;
}

export const IMPACT_KO: Record<Impact, string> = {
  blocks: "통제",
  unknown: "미확인",
};

export const LEG_KO: Record<LegKind, string> = {
  sidewalk: "보도",
  crosswalk: "횡단보도",
  underpass: "지하보도",
  overpass: "육교",
  stairs: "계단",
  elevator: "엘리베이터",
  station: "역 통과",
};

export const EVIDENCE_KO: Record<EvidenceKind, string> = {
  notice: "공지",
  timetable: "시각표",
  topis_incident: "돌발",
  bus_skip: "버스 우회",
  bus_return: "버스 복귀",
  rtd_spike: "혼잡 급등",
};

const KST_OFFSET_MIN = 9 * 60;

/** ISO 8601(+오프셋) → "HH:MM" (KST 기준) */
export function hhmm(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const kst = new Date(d.getTime() + KST_OFFSET_MIN * 60_000);
  const h = String(kst.getUTCHours()).padStart(2, "0");
  const m = String(kst.getUTCMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

/** 창 표기 "06:00–09:20". end 가 없으면 "06:00–종료 미정" */
export function windowKo(start: string | null | undefined, end: string | null | undefined): string {
  return `${hhmm(start)}–${end ? hhmm(end) : "종료 미정"}`;
}

/** t 기준 남은 시간 문구: "40분 뒤 해제", "2시간 10분 뒤 해제", 지났으면 "해제됨" */
export function untilKo(end: string | null | undefined, t: string): string {
  if (!end) return "종료 미정";
  const diffMin = Math.round((new Date(end).getTime() - new Date(t).getTime()) / 60_000);
  if (diffMin <= 0) return "해제됨";
  if (diffMin < 60) return `${diffMin}분 뒤 해제`;
  const h = Math.floor(diffMin / 60);
  const m = diffMin % 60;
  return m ? `${h}시간 ${m}분 뒤 해제` : `${h}시간 뒤 해제`;
}
