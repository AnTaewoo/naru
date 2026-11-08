// enum 코드값 → 한국어 라벨. 한국어는 이 파일에만 (INTERFACE §4, CONVENTIONS §5.8)
import type {
  ClosureType,
  Evidence,
  EvidenceKind,
  Impact,
  LegKind,
  Status,
} from "../types/contracts";

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
  const type = reasonType(reason);
  return type ? TYPE_KO[type] + reason.slice(type.length) : reason;
}

/** reason 앞머리의 type 코드값 ("marathon 1구간 …" → marathon). 자유 문장이면 null */
export function reasonType(reason: string): ClosureType | null {
  const space = reason.indexOf(" ");
  const head = space < 0 ? reason : reason.slice(0, space);
  return head in TYPE_KO ? (head as ClosureType) : null;
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

/** t 와 같은 날(KST)이면 "HH:MM", 다른 날이면 "M/D HH:MM" — 근거 시각 (시각표 게시일 등) */
export function whenKo(at: string | null | undefined, t: string): string {
  if (!at || Number.isNaN(new Date(at).getTime())) return "—";
  const day = (iso: string) => new Date(new Date(iso).getTime() + KST_OFFSET_MIN * 60_000);
  const a = day(at);
  const b = day(t);
  const sameDay =
    a.getUTCFullYear() === b.getUTCFullYear() &&
    a.getUTCMonth() === b.getUTCMonth() &&
    a.getUTCDate() === b.getUTCDate();
  return sameDay ? hhmm(at) : `${a.getUTCMonth() + 1}/${a.getUTCDate()} ${hhmm(at)}`;
}

/** 거리: 1 km 아래는 m 반올림("840m"), 넘으면 km 소수 한 자리("1.7km") */
export function distanceKo(m: number): string {
  const r = Math.round(m);
  return r < 1000 ? `${r}m` : `${(m / 1000).toFixed(1)}km`;
}

/** 조사 "로/으로" — 받침이 없거나 ㄹ 받침이면 "로". 한글로 끝나지 않으면 "(으)로" */
export function josaRo(word: string): string {
  const code = word.trimEnd().codePointAt(word.trimEnd().length - 1) ?? 0;
  if (code < 0xac00 || code > 0xd7a3) return "(으)로";
  const jong = (code - 0xac00) % 28;
  return jong === 0 || jong === 8 ? "로" : "으로";
}

/** 길찾기 안내 문장 (시안 02 하단 note). crossing = 경로가 건너는 지하보도·육교 이름 */
export function routeNoteKo(p: {
  crosswalks: number;
  until: string | null;
  blocked: boolean;
  crossing: string | null;
}): string {
  if (p.crosswalks === 0) return "이 시각엔 경로에 걸린 통제가 없어요.";
  const via = p.crossing ? `${p.crossing}${josaRo(p.crossing)} 건너는` : null;
  const until = p.until ? `${hhmm(p.until)}까지 ` : "";
  if (!p.blocked) {
    // 예정만 피했다 — 공지 창 안이라 피했지만 현장 확인은 아직 (ADR-011 A)
    return `횡단보도 ${p.crosswalks}곳이 ${until}공지상 통제 시간(현장 확인 전)이라 ${via ?? "피해 가는"} 길을 골랐어요.`;
  }
  return `횡단보도 ${p.crosswalks}곳이 ${until}막혀 있어 ${via ?? "돌아가는"} 길을 골랐어요.`;
}

/**
 * 근거 한 줄 (시안 03 "이렇게 판단했어요"): detail 의 상태 전이 → 구간 label·section → 공지 excerpt 순.
 * 없으면 근거 종류 라벨. 기준 시각보다 뒤의 전이(해제 등)는 "예정"
 */
export function evidenceTextKo(e: Evidence, t: string): string {
  const d = e.detail ?? {};
  const transition = d["transition"];
  if (typeof transition === "string") {
    const [a, b] = transition.split("→");
    if (a && b && a in STATUS_KO && b in STATUS_KO) {
      const future = new Date(e.at).getTime() > new Date(t).getTime();
      return `${STATUS_KO[a as Status]} → ${STATUS_KO[b as Status]}${future ? " 예정" : ""}`;
    }
  }
  const parts = [d["label"], d["section"]].filter(
    (x): x is string => typeof x === "string" && x !== "",
  );
  if (parts.length > 0) return parts.join(" ");
  if (typeof d["excerpt"] === "string") return d["excerpt"];
  return EVIDENCE_KO[e.kind];
}

/** /route 오류 코드(INTERFACE §6) → 화면 문구 */
export const ROUTE_ERROR_KO: Record<string, string> = {
  no_route: "이 시각엔 갈 수 있는 길을 찾지 못했어요",
  invalid_query: "출발·도착을 다시 골라 주세요",
  out_of_coverage: "이 위치는 아직 길찾기 범위(종로·중구) 밖이에요", // ADR-011, INTERFACE §6
};

/** 경로가 피한 통제의 상태 (ADR-011 A) — confirmed 는 막힘, scheduled 는 공지상 시간이라 피했을 뿐 */
export const AVOIDED_STATUS_KO: Partial<Record<Status, string>> = {
  confirmed: "통제 중",
  scheduled: "공지상 통제 시간 · 현장 확인 전",
};

export function routeErrorKo(code: string | null): string {
  return (code && ROUTE_ERROR_KO[code]) || "경로를 받지 못했어요. 잠시 뒤 다시 해 주세요";
}

const WEEKDAY_KO = ["일", "월", "화", "수", "목", "금", "토"];

function kstParts(iso: string): { y: number; m: number; d: number; wd: number } | null {
  const ms = new Date(iso).getTime();
  if (Number.isNaN(ms)) return null;
  const k = new Date(ms + KST_OFFSET_MIN * 60_000);
  return { y: k.getUTCFullYear(), m: k.getUTCMonth() + 1, d: k.getUTCDate(), wd: k.getUTCDay() };
}

/** "3월 15일" (KST). 시각이 없으면 "시간 미정" */
export function dateKo(iso: string | null | undefined): string {
  const p = iso ? kstParts(iso) : null;
  return p ? `${p.m}월 ${p.d}일` : "시간 미정";
}

/** "3월 15일 (일)" (KST) — 통제 불러오기의 날짜 머리 */
export function dayKo(iso: string | null | undefined): string {
  const p = iso ? kstParts(iso) : null;
  return p ? `${p.m}월 ${p.d}일 (${WEEKDAY_KO[p.wd] ?? ""})` : "시간 미정";
}

/** 하단 시트 제목 — 기준 시각 t 가 지금과 같은 날(KST)이면 "오늘 통제", 아니면 "3월 15일 통제" */
export function sheetTitleKo(t: string, nowMs: number): string {
  const a = kstParts(t);
  const b = kstParts(new Date(nowMs).toISOString());
  const same = a !== null && b !== null && a.y === b.y && a.m === b.m && a.d === b.d;
  return same ? "오늘 통제" : `${dateKo(t)} 통제`;
}
