// enum 코드값 → 한국어 라벨. 한국어는 이 파일에만 (INTERFACE §4, CONVENTIONS §5.8)
import type {
  ClosureEvent,
  ClosureType,
  DataAsOf,
  EvidenceKind,
  Impact,
  LegKind,
  Source,
  Status,
  SummarySegment,
} from "../types/contracts";
import {
  RELEASE_GRACE_MS,
  confidenceLevel,
  eventKind,
  kstDay,
  type ChipKind,
  type ConfidenceLevel,
} from "../map/eventKinds";
import type { ExampleKey } from "../map/examples";
import type { ReportFailure, ReportValue } from "../state/report";

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

/** 지금 지도 칩 (T7.4) — 사건 종류. 예정 = 1시간 안 + 오늘·내일 */
export const CHIP_KO: Record<ChipKind, string> = {
  confirmed: "통제 중",
  scheduled: "예정",
  zone: "예정 구역",
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

/** 해제 예정 뒤 정리 시간이 끝나는 시각 (BE: 끝 + 30분에 released) */
export function graceEndIso(end: string): string {
  return new Date(Date.parse(end) + RELEASE_GRACE_MS).toISOString();
}

/** 해제 예정 시각은 지났지만 정리 시간(30분) 안 — 아직 통제 중이다 */
export function inGrace(end: string | null | undefined, atMs: number): boolean {
  const e = end ? Date.parse(end) : Number.NaN;
  return !Number.isNaN(e) && atMs >= e && atMs < e + RELEASE_GRACE_MS;
}

/** 정리 시간이 왜 있는지 한 줄 (태우 11/10 — "왜 30분 더 못 가지?") */
export const GRACE_NOTE_KO = "해제 예정 시각 뒤 30분은 현장 정리로 막힌 걸로 봐요";

/**
 * t 기준 남은 시간 문구: "40분 뒤 해제", "2시간 10분 뒤 해제", 해제 예정이 지났으면 30분은 "정리 중 · 08:38까지",
 * 그 뒤 "해제됨"
 */
export function untilKo(end: string | null | undefined, t: string): string {
  if (!end) return "종료 미정";
  const ms = Date.parse(end) - Date.parse(t);
  const diffMin = Math.round(ms / 60_000);
  if (diffMin <= 0) {
    return ms > -RELEASE_GRACE_MS ? `정리 중 · ${hhmm(graceEndIso(end))}까지` : "해제됨";
  }
  if (diffMin < 60) return `${diffMin}분 뒤 해제`;
  const h = Math.floor(diffMin / 60);
  const m = diffMin % 60;
  return m ? `${h}시간 ${m}분 뒤 해제` : `${h}시간 뒤 해제`;
}

/** "45분", "1시간 20분", "2시간" — 분 단위 반올림 */
export function durationKo(ms: number): string {
  const min = Math.max(0, Math.round(ms / 60_000));
  if (min < 60) return `${min}분`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m ? `${h}시간 ${m}분` : `${h}시간`;
}

/**
 * 사건 남은 시간 (T7.5) — 통제 중 "16:00 해제 예정"(지났으면 정리 시간 "16:30까지 정리 중"), 예정 "1시간 20분 뒤
 * 시작", 시작 시각이 지났는데 근거가 없어 아직 예정이면 "12:00 시작 · 확인 전", 해제 "13:00 해제"
 */
export function remainKo(e: Pick<ClosureEvent, "status" | "window">, atMs: number): string {
  const { start, end } = e.window;
  if (e.status === "confirmed") {
    if (!end) return "해제 시각 미정";
    return atMs < Date.parse(end)
      ? `${hhmm(end)} 해제 예정`
      : `${hhmm(graceEndIso(end))}까지 정리 중`;
  }
  if (e.status === "released") return end ? `${hhmm(end)} 해제` : "해제";
  if (!start) return "시작 시각 미정";
  const ms = Date.parse(start) - atMs;
  return ms > 0 ? `${durationKo(ms)} 뒤 시작` : `${hhmm(start)} 시작 · 확인 전`;
}

/** 예시로 보기 (T7.11, 태우 11/10) — 데모 날짜·시각 */
export const EXAMPLE_KO: Record<ExampleKey, { chip: string; title: string; sub: string }> = {
  marathon: { chip: "3/15 서울마라톤", title: "2026 서울마라톤", sub: "3월 15일 07:45 광화문" },
  rally: { chip: "11/7 광화문 집회", title: "광화문 집회·행진", sub: "11월 7일 15:00 세종대로" },
  march: { chip: "11/9 국회대로 행진", title: "국회대로 행진", sub: "11월 9일 12:00" },
};

/** 시트 세 묶음 (T7.12) — 다가오는 통제 날짜 머리: 기준 시각의 KST 날짜로 오늘·내일, 그 밖은 "11월 9일 (월)" */
export function dayLabelKo(day: string, atMs: number): string {
  if (day === kstDay(atMs)) return "오늘";
  if (day === kstDay(atMs + 24 * 60 * 60_000)) return "내일";
  return dayKo(`${day}T12:00:00+09:00`);
}

/** 지금이 아닌 시각을 볼 때 시트 위 (T7.12) — "11월 7일 15:00 기준" */
export function bannerKo(t: string): string {
  return `${dateKo(t)} ${hhmm(t)} 기준`;
}

/** 지금 묶음이 비면 (T7.12) — 빈 화면 대신 한 줄 + 다가오는·지난 통제 */
export function nowEmptyKo(live: boolean): string {
  return live ? "지금 서울에 걸린 통제가 없어요" : "이 시각 서울에 걸린 통제가 없어요";
}

/** 시트 세 묶음 머리 (T7.12) — 기준 시각이 지금이 아니면 "지금" 대신 "이 시각" */
export const SECTION_KO = {
  now: "지금",
  nowAt: "이 시각",
  upcoming: "다가오는 통제",
  past: "지난 통제",
} as const;

/** 지난 통제 나머지 (T7.12) */
export function moreKo(n: number): string {
  return `더 보기 (${n})`;
}

/** 사건 카드 상태 배지 (T7.5) — 1시간 안이어도 시작 시각이 지났으면(근거 없는 예정) "확인 전" */
export function kindBadgeKo(e: ClosureEvent, atMs: number): string {
  const kind = eventKind(e, atMs);
  if (kind === "soon") {
    const start = e.window.start ? Date.parse(e.window.start) : Number.NaN;
    return start > atMs ? "곧 시작" : "확인 전";
  }
  return { confirmed: "통제 중", scheduled: "예정", zone: "예정 구역", released: "해제" }[kind];
}

/** 목록 행 오른쪽 (T7.5) — 통제 중 "23분 뒤 해제", 예정 "1시간 27분 뒤 시작", 시작했는데 근거 없으면 "확인 전" */
export function rowBadgeKo(e: ClosureEvent, atMs: number): string {
  if (e.status === "confirmed") return untilKo(e.window.end ?? null, new Date(atMs).toISOString());
  if (e.status === "released") return "해제";
  const start = e.window.start ? Date.parse(e.window.start) : Number.NaN;
  return start > atMs ? `${durationKo(start - atMs)} 뒤 시작` : "확인 전";
}

/**
 * 시트 목록 행 배지 (T7.12) — 지난 통제는 그 날짜 "3월 15일"(묶음에 날짜가 없다), 다른 날 시작하는 다가오는 통제는
 * "예정"·"예정 구역"(날짜는 묶음 머리 — 365일 창이라 "4,000시간 뒤" 를 피한다), 그 밖은 rowBadgeKo
 */
export function sheetBadgeKo(e: ClosureEvent, atMs: number): string {
  const kind = eventKind(e, atMs);
  if (kind === "released") return dateKo(e.window.start ?? e.window.end);
  const start = e.window.start ? Date.parse(e.window.start) : Number.NaN;
  const otherDay = !Number.isNaN(start) && kstDay(start) !== kstDay(atMs);
  if ((kind === "scheduled" || kind === "zone") && otherDay) return kindBadgeKo(e, atMs);
  return rowBadgeKo(e, atMs);
}

export const SOURCE_KO: Record<Source, string> = {
  course: "마라톤 시간표",
  smpa: "경찰청 공지",
  topis: "TOPIS 공지",
  news: "보도",
  seoul_press: "서울시 보도자료",
  incident: "TOPIS 돌발",
  bus: "버스",
  rtd: "실시간 혼잡",
};

/** 출처 (T7.5) — TOPIS 통제지도 예정 통제(T7.3)는 출처가 topis 라 공지 id(topismap-)로 가른다 */
export function sourceKo(e: Pick<ClosureEvent, "source" | "notice">): string {
  if (e.notice?.notice_id.startsWith("topismap-")) return "TOPIS 통제지도";
  return e.source ? SOURCE_KO[e.source] : "출처 미상";
}

/** 확신도 3단계 문구 (P7 계획) — 카드·통제 근거가 같은 말. 판정은 eventKinds.confidenceLevel 하나 (T7.14) */
export const CONFIDENCE_KO: Record<ConfidenceLevel, string> = {
  high: "높음",
  mid: "보통",
  low: "낮음",
};

/** 0.8 이상 높음, 0.7 이상 보통, 그 아래 낮음 */
export function confidenceKo(c: number): string {
  return CONFIDENCE_KO[confidenceLevel(c)];
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

/**
 * 길찾기 안내 문장 (시안 02 하단 note). crossing = 경로가 건너는 지하보도·육교 이름.
 * requested = 그중 "이 구역 피해서"로 피한 곳(T7.6), avoiding = 피할 구역을 골랐는지
 */
export function routeNoteKo(p: {
  crosswalks: number;
  until: string | null;
  blocked: boolean;
  crossing: string | null;
  requested?: number;
  avoiding?: boolean;
  /** 경로 시각 — 해제 예정(until)이 지났으면 정리 시간 끝까지로 쓴다 (태우 11/10) */
  t?: string;
}): string {
  if (p.crosswalks === 0) {
    return p.avoiding
      ? "이 길은 고른 구역을 지나지 않아요."
      : "이 시각엔 경로에 걸린 통제가 없어요.";
  }
  const via = p.crossing ? `${p.crossing}${josaRo(p.crossing)} 건너는` : null;
  const until = p.until ? `${hhmm(p.until)}까지 ` : "";
  const ruled = p.crosswalks - (p.requested ?? 0); // 상태(통제 중·공지상 시간)로 피한 곳
  if (ruled === 0)
    return `고른 구역의 횡단보도 ${p.crosswalks}곳을 피해 ${via ?? "돌아가는"} 길을 골랐어요.`;
  if (!p.blocked) {
    // 예정만 피했다 — 공지 창 안이라 피했지만 현장 확인은 아직 (ADR-011 A)
    return `횡단보도 ${ruled}곳이 ${until}공지상 통제 시간(현장 확인 전)이라 ${via ?? "피해 가는"} 길을 골랐어요.`;
  }
  if (p.until && p.t && Date.parse(p.t) >= Date.parse(p.until)) {
    const grace = hhmm(graceEndIso(p.until));
    return `횡단보도 ${ruled}곳이 ${grace}까지 정리 중이라 ${via ?? "돌아가는"} 길을 골랐어요.`;
  }
  return `횡단보도 ${ruled}곳이 ${until}막혀 있어 ${via ?? "돌아가는"} 길을 골랐어요.`;
}

/** 검색한 장소 카드 (T7.14) — 버튼, 홈 검색칸이 비었을 때 저장한 장소 머리 */
export const PLACE_KO = {
  from: "출발",
  to: "도착",
  save: "☆ 저장",
  saved: "★ 저장됨",
  close: "장소 닫기",
  savedHead: "저장한 장소",
} as const;

/** 이 구역 피해서 길찾기 (T7.6) — 사건 카드 버튼, 길찾기 시트 맨 위 줄 */
export const AVOID_KO = { button: "이 구역 피해서 길찾기", remove: "빼기" } as const;

export function avoidBannerKo(title: string | null): string {
  return `피하는 구역 · ${title ?? "고른 통제"}`;
}

/** /route 오류 코드(INTERFACE §6) → 화면 문구 */
export const ROUTE_ERROR_KO: Record<string, string> = {
  no_route: "이 시각엔 갈 수 있는 길을 찾지 못했어요",
  invalid_query: "출발·도착을 다시 골라 주세요",
  out_of_coverage: "이 위치는 아직 길찾기 범위(서울) 밖이에요", // ADR-011, INTERFACE §6
};

/** 경로가 피한 통제의 상태 (ADR-011 A) — confirmed 는 막힘, scheduled 는 공지상 시간이라 피했을 뿐 */
export const AVOIDED_STATUS_KO: Partial<Record<Status, string>> = {
  confirmed: "통제 중",
  scheduled: "공지상 통제 시간 · 현장 확인 전",
};

export function routeErrorKo(code: string | null): string {
  return (code && ROUTE_ERROR_KO[code]) || "경로를 받지 못했어요. 잠시 뒤 다시 해 주세요";
}

// 내 위치 (T5.7)
export const MY_LOCATION_KO = "내 위치";
export const LOCATING_KO = "내 위치 찾는 중…";
const OD_KO = { from: "출발", to: "도착" } as const;

/** 출발·도착 칸이 비었을 때 */
export function odHintKo(which: "from" | "to"): string {
  return `지도를 눌러 ${OD_KO[which]}을 고르세요`;
}

/** 출발·도착 칸 옆 버튼 이름 — "출발을 내 위치로" */
export function locateButtonKo(which: "from" | "to"): string {
  return `${OD_KO[which]}을 내 위치로`;
}

/** 내 위치를 칸에 못 넣었을 때 안내 — 칸은 비워 두고 지도로 고르게 한다 */
export function locateNoteKo(
  which: "from" | "to",
  status: "locating" | "denied" | "unavailable" | "outside",
): string {
  switch (status) {
    case "locating":
      return `내 위치를 찾고 있어요. 지도를 눌러 ${OD_KO[which]}을 골라도 돼요`;
    case "denied":
      return `위치 권한이 꺼져 있어요. ${odHintKo(which)}`;
    case "unavailable":
      return `내 위치를 찾지 못했어요. ${odHintKo(which)}`;
    case "outside":
      return `내 위치가 길찾기 범위(서울) 밖이에요. ${odHintKo(which)}`;
  }
}

// 주소·검색 (T5.8) — 좌표는 화면에 쓰지 않는다
export const SELECTED_PLACE_KO = "선택한 위치";
export const SEARCH_PLACEHOLDER_KO = "장소·주소 검색";

/** 칸 입력칸 안내 — "출발 검색 또는 지도 누르기" */
export function fieldSearchPlaceholderKo(which: "from" | "to"): string {
  return `${OD_KO[which]} 검색 또는 지도 누르기`;
}

/** 검색 결과 칸의 한 줄 — 칸 입력(inField)이면 지도로 골라도 된다고 덧붙인다 */
export function searchStatusKo(
  status: "short" | "loading" | "empty" | "error",
  inField: boolean,
): string {
  switch (status) {
    case "short":
      return inField ? "두 글자 이상 입력하거나 지도를 누르세요" : "두 글자 이상 입력하세요";
    case "loading":
      return "찾는 중…";
    case "empty":
      return inField ? "찾는 곳이 없어요. 지도를 눌러 고르세요" : "찾는 곳이 없어요";
    case "error":
      return inField ? "검색을 못 했어요. 지도를 눌러 고르세요" : "검색을 못 했어요";
  }
}

/** 지도 오른쪽 위 '내 위치 찾기'(GeolocateControl) 결과가 보행망 밖일 때 */
export const MAP_OUTSIDE_KO = "내 위치는 아직 길찾기 범위(서울) 밖이에요";

/** 행진 예상 위치 (T7.16, ADR-015 G) — 공지 일정으로 계산한 값, 실제 추적처럼 보이는 말은 쓰지 않는다 */
export const MARCH_KO = {
  basis: "공지 일정 기준 예상 위치",
  play: "예상 위치 재생",
  stop: "정지",
  playing: "통제 시간 전체를 12초에",
} as const;

export function marchProbabilityKo(p: number): string {
  return `이 시각 막혀 있을 확률 ${Math.round(p * 100)}%`;
}

/** 알림 켜기 (T7.7, ADR-014 C) — 구독·관심 지역은 T7.8~T7.10, 그때까지는 허용만 */
export const PUSH_KO = {
  title: "통제 알림",
  why: "관심 지역 근처에 통제가 생기면 알려 드려요",
  enable: "통제 알림 받기",
  working: "알림을 켜는 중…",
  on: "알림 받는 중",
  off: "알림 끄기",
  granted: "알림이 허용됐어요. 장소를 검색해 ☆ 이 근처 알림 받기로 관심 지역을 더하세요",
  denied: "알림이 꺼져 있어요. 브라우저 설정에서 이 사이트의 알림을 허용하면 받을 수 있어요",
  iosInstall:
    "iPhone·iPad 는 홈 화면에 추가한 뒤에 알림을 켤 수 있어요 — 공유 버튼 → '홈 화면에 추가' (iOS 16.4 이상)",
  unsupported: "이 브라우저는 알림을 지원하지 않아요",
  failed: "알림 구독을 만들지 못했어요. 시크릿 창이거나 푸시 서비스에 닿지 못했을 수 있어요",
  areasHead: "관심 지역",
  noAreas: "아직 관심 지역이 없어요 — 장소를 검색해 ☆ 이 근처 알림 받기",
  limit: "저장 관심 지역은 10곳까지예요",
  lastSeen: "마지막 위치 근처",
  remove: "빼기",
  watch: "☆ 이 근처 알림 받기",
  watching: "★ 이 근처 알림 받는 중",
  privacy:
    "저장하는 건 구독 주소와 관심 지역 좌표뿐이에요. 마지막 위치는 150 m 단위로 3시간만 — 자세한 건 고지",
} as const;

/** 관심 지역 한 줄 — "종로구 종로 1 · 500 m", 마지막 위치면 "마지막 위치 근처 · 500 m" */
export function watchAreaKo(label: string | null, radiusM: number, lastSeen: boolean): string {
  const where = lastSeen ? PUSH_KO.lastSeen : (label ?? SELECTED_PLACE_KO);
  return `${where} · ${radiusM} m`;
}

/** 통제 제보 (T7.15, INTERFACE §8) — 기록만, 길찾기에는 아직 안 쓴다 */
export const REPORT_KO = {
  button: "통제 제보",
  control: "제보",
  title: "이 횡단보도가 맞나요?",
  blocked: "막혔어요",
  open: "열렸어요",
  close: "제보 닫기",
  locating: "지금 위치를 찾고 있어요…",
  finding: "가까운 횡단보도를 찾고 있어요…",
  sending: "보내는 중…",
  note: "제보는 기록만 해요 — 아직 길찾기에는 쓰지 않아요",
  field: "현장 검증",
  retry: "다시 하기",
} as const;

export const REPORT_FAILURE_KO: Record<ReportFailure, string> = {
  denied: "위치 권한이 꺼져 있어 제보할 수 없어요",
  unavailable: "지금 위치를 찾지 못했어요",
  inaccurate: "위치가 정확하지 않아요. 트인 곳에서 다시 해 주세요",
  none: "가까운 횡단보도를 찾지 못했어요. 횡단보도 옆에서 다시 해 주세요",
  too_many: "이 횡단보도는 방금 제보했어요. 조금 뒤에 다시 할 수 있어요",
  failed: "제보를 보내지 못했어요",
};

/** "여기서 71 m · 위치 정확도 ±14 m" */
export function reportWhereKo(distanceM: number, accuracyM: number | null): string {
  const where = `여기서 ${distanceM} m`;
  return accuracyM === null ? where : `${where} · 위치 정확도 ±${accuracyM} m`;
}

export function reportSentKo(value: ReportValue): string {
  return `${value === "blocked" ? "막혔다고" : "열렸다고"} 제보했어요. 고마워요!`;
}

/** 통제 근거의 제보 줄 — 0건이면 줄을 안 쓴다 */
export function reportCountKo(c: { blocked: number; open: number } | null): string | null {
  const n = c ? c.blocked + c.open : 0;
  return c && n > 0 ? `최근 1시간 제보 ${n}건 (막힘 ${c.blocked} · 열림 ${c.open})` : null;
}

/**
 * maplibre 컨트롤 문구 — 쓰는 컨트롤 것만. 키는 설치된 maplibre-gl 6.16.0 의 기본 영어 표
 * (node_modules/maplibre-gl/dist/maplibre-gl-dev.mjs 의 defaultLocale)에서 확인
 */
export const MAP_LOCALE_KO: Record<string, string> = {
  "Map.Title": "지도 화면",
  "NavigationControl.ZoomIn": "확대",
  "NavigationControl.ZoomOut": "축소",
  "GeolocateControl.FindMyLocation": "내 위치 찾기",
  "GeolocateControl.LocationNotAvailable": "내 위치를 쓸 수 없어요",
};

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

/** 시트 제목 — 지금을 보면 "지금 서울 통제", 아니면 "서울 통제"(날짜·시각은 시트 맨 위 기준 줄 bannerKo, T7.12) */
export function liveTitleKo(live: boolean): string {
  return live ? "지금 서울 통제" : "서울 통제";
}

/** 하단 시트 제목 — 기준 시각 t 가 지금과 같은 날(KST)이면 "오늘 통제", 아니면 "3월 15일 통제" */
export function sheetTitleKo(t: string, nowMs: number): string {
  const a = kstParts(t);
  const b = kstParts(new Date(nowMs).toISOString());
  const same = a !== null && b !== null && a.y === b.y && a.m === b.m && a.d === b.d;
  return same ? "오늘 통제" : `${dateKo(t)} 통제`;
}

// 통제 목록 문구 (T5.9, ADR-012) — 제목·둘째 줄은 파서 요약(구조화 칸)으로. 문장·숫자 표기는 여기서만
type EventLike = Pick<ClosureEvent, "reason" | "type" | "summary">;

function uniq(xs: string[]): string[] {
  return xs.filter((x, i) => xs.indexOf(x) === i);
}

/** 경유가 이보다 많으면 제목은 처음·끝만 — 지나는 곳 전부는 카드의 longRouteKo (T7.5) */
const MAX_VIA = 2;
/** 둘째 줄 도로는 이만큼까지, 나머지는 "외 N곳" */
const MAX_ROADS = 3;

/** 구간 경로 전부 "A → B → C" (via 포함, 같은 이름이 이어지면 하나로) */
function fullPathKo(s: SummarySegment): string {
  const names = [s.from_, ...(s.via ?? []), s.to];
  return names.filter((n, i) => i === 0 || n !== names[i - 1]).join(" → ");
}

/** 제목용 구간 경로 — 경유가 MAX_VIA 보다 많으면 "A → Z" */
function pathKo(s: SummarySegment): string {
  return (s.via ?? []).length > MAX_VIA ? `${s.from_} → ${s.to}` : fullPathKo(s);
}

/** 제목에서 줄인 긴 경로의 전부 — 없으면 null (사건 카드, T7.5) */
export function longRouteKo(e: Pick<ClosureEvent, "summary">): string | null {
  const long = (e.summary?.segments ?? []).filter((x) => (x.via ?? []).length > MAX_VIA);
  return long.length ? long.map(fullPathKo).join(", ") : null;
}

/**
 * 사건 제목 — 공지 "A~B → C·D" 는 "A~B 집회 → C·D 행진"(첫 구간 끝에서 갈라지는 구간이 행진),
 * 그 밖은 구간 경로·지점 이름 + 종류. 요약이 없으면(마라톤 등) reason
 */
export function eventTitleKo(e: EventLike): string {
  const segs = e.summary?.segments ?? [];
  const points = e.summary?.points ?? [];
  const label = e.type ? TYPE_KO[e.type] : "";
  const [first, ...rest] = segs;
  if (first) {
    const branches = uniq(rest.filter((x) => x.from_ === first.to).map((x) => x.to));
    if (branches.length > 0 && first.from_ !== first.to) {
      return `${first.from_}~${first.to} ${TYPE_KO.rally} → ${branches.join("·")} ${TYPE_KO.march}`;
    }
    const body = segs.map((x) =>
      e.type === "rally" ? (x.from_ === x.to ? x.from_ : `${x.from_}~${x.to}`) : pathKo(x),
    );
    return `${uniq(body).join(", ")} ${label}`.trim();
  }
  if (points.length > 0) return `${uniq(points).join("·")} ${label}`.trim();
  return reasonKo(e.reason);
}

/** 인원 — 만 명부터는 "5만 명"(소수 한 자리까지), 그 아래는 "5,000명" */
export function peopleKo(n: number): string {
  if (n >= 10_000) return `${Math.round(n / 1_000) / 10}만 명`;
  return `${n.toLocaleString("ko-KR")}명`;
}

/** 사건 둘째 줄 — "5만 명 · 태평로". 요약이 없으면 빈 문자열 */
export function eventDetailKo(e: Pick<ClosureEvent, "summary">): string {
  const s = e.summary;
  if (!s) return "";
  const people = s.reported_people ?? null;
  const all = s.roads ?? [];
  const roads =
    all.length > MAX_ROADS
      ? `${all.slice(0, MAX_ROADS).join("·")} 외 ${all.length - MAX_ROADS}곳`
      : all.join("·");
  return [people === null ? "" : peopleKo(people), roads].filter(Boolean).join(" · ");
}

/** 실시간 출처가 이 분보다 오래 안 바뀌면 회색 경고 (결정 C) */
export const DATA_STALE_MIN = 30;

/** 시각이 없거나 maxMin 분보다 오래면 true */
export function isStale(
  at: string | null | undefined,
  nowMs: number,
  maxMin = DATA_STALE_MIN,
): boolean {
  const t = at ? Date.parse(at) : Number.NaN;
  return Number.isNaN(t) || nowMs - t > maxMin * 60_000;
}

function monthDayKo(iso: string): string {
  const p = kstParts(iso);
  return p ? `${p.m}/${p.d}` : "";
}

/**
 * 통제 정보 멈춤 경고 (T7.13, 태우 11/10) — TOPIS 돌발 배치를 마지막으로 받은 시각(data_as_of.topis_incident, 빈 배치
 * 포함)이 30분보다 오래면 "통제 정보가 N분째 갱신되지 않았어요"(시간·일 단위로 올림 없이). 받은 적 없음(null)은 경고 없음
 */
export function staleWarningKo(a: DataAsOf | null | undefined, nowMs: number): string | null {
  const at = a?.topis_incident ? Date.parse(a.topis_incident) : Number.NaN;
  if (Number.isNaN(at) || nowMs - at <= DATA_STALE_MIN * 60_000) return null;
  const min = Math.floor((nowMs - at) / 60_000);
  const span =
    min < 60
      ? `${min}분`
      : min < 24 * 60
        ? `${Math.floor(min / 60)}시간`
        : `${Math.floor(min / (24 * 60))}일`;
  return `통제 정보가 ${span}째 갱신되지 않았어요`;
}

/**
 * /licenses 데이터 기준 시각(T7.13 — T5.9 땐 목록 위) — "TOPIS 13:25 · 경찰청 11/6 공지 · 마라톤 3/12 시각표 기준".
 * 실시간 돌발(TOPIS)이 없거나 30분 넘게 안 바뀌었으면 회색 경고 한 줄
 */
export function dataAsOfKo(a: DataAsOf, nowMs: number): { text: string; warning: string | null } {
  const parts: string[] = [];
  if (a.topis_incident) parts.push(`TOPIS ${hhmm(a.topis_incident)}`);
  if (a.smpa) parts.push(`경찰청 ${monthDayKo(a.smpa)} 공지`);
  if (a.topis_notice) parts.push(`TOPIS ${monthDayKo(a.topis_notice)} 공지`);
  if (a.course) parts.push(`마라톤 ${monthDayKo(a.course)} 시각표`);
  const text = parts.length ? `${parts.join(" · ")} 기준` : "받은 통제 정보가 없어요";
  const warning = !a.topis_incident
    ? "실시간 돌발(TOPIS)은 아직 받지 않아요"
    : isStale(a.topis_incident, nowMs)
      ? `실시간 돌발(TOPIS)이 ${DATA_STALE_MIN}분 넘게 안 바뀌었어요`
      : null;
  return { text, warning };
}
