// enum 코드값 → 한국어 라벨. 한국어는 이 파일에만 (INTERFACE §4, CONVENTIONS §5.8)
import type {
  ClosureEvent,
  ClosureType,
  DataAsOf,
  EvidenceKind,
  Impact,
  LegKind,
  Status,
  SummarySegment,
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

/** 구간 경로 "A → B → C" (via 포함, 같은 이름이 이어지면 하나로) */
function pathKo(s: SummarySegment): string {
  const names = [s.from_, ...(s.via ?? []), s.to];
  return names.filter((n, i) => i === 0 || n !== names[i - 1]).join(" → ");
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
  const roads = (s.roads ?? []).join("·");
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
 * 목록 위 기준 시각 — "TOPIS 13:25 · 경찰청 11/6 공지 · 마라톤 3/12 시각표 기준".
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
