// 통제 목록 문구 (T5.9, ADR-012) — 제목·둘째 줄·인원·기준 시각은 FE 템플릿. 입력은 recorded
// naru_api/closure_events.json(v0.12 재기록): 공지 r04·r01 의 summary, 코스는 summary 없음, data_as_of
import { describe, expect, it } from "vitest";
import {
  eventById,
  recorded,
  recordedCandidate,
  recordedEvents,
  recordedLive,
  recordedNoticeItems,
} from "../test/recorded";
import type { ClosureEvent } from "../types/contracts";
import {
  CONFIDENCE_KO,
  confidenceKo,
  dataAsOfKo,
  bannerKo,
  dayLabelKo,
  kindBadgeKo,
  nowEmptyKo,
  rowBadgeKo,
  sheetBadgeKo,
  eventDetailKo,
  eventTitleKo,
  isStale,
  liveTitleKo,
  longRouteKo,
  peopleKo,
  GRACE_NOTE_KO,
  remainKo,
  untilKo,
  sourceKo,
  staleWarningKo,
} from "./ko";

const res = recordedEvents();
function bySentence(id: string): ClosureEvent {
  const e = res.events.find((x) => x.notice?.sentence_id === id);
  if (!e) throw new Error(`기록에 ${id} 사건이 없다 — make record-naru-api`);
  return e;
}
const rally = bySentence("smpa-20261107-r04");
const loop = bySentence("smpa-20261107-r01");
const seg1 = res.events.find((e) => e.reason.startsWith("marathon 1구간"));

describe("통제 목록 문구 (T5.9)", () => {
  it("제목은 파서 요약 칸으로 — '~' 구간에서 갈라지는 '→' 는 집회 → 행진, 요약이 없으면 reason", () => {
    expect(eventTitleKo(rally)).toBe("시의회~숭례문오거리 집회 → 광화문·고용노동청 행진");
    expect(eventTitleKo(loop)).toBe("동화면세점 앞 → 종로1가사거리 → 동화면세점 앞 행진");
    if (!seg1) throw new Error("마라톤 1구간 없음");
    expect(eventTitleKo(seg1)).toBe("마라톤 1구간 세종대로 사거리~숭례문 오거리");
  });

  it("둘째 줄 — 인원·도로, 만 단위 표기는 FE 가 (recorded summary 의 숫자 그대로 받아서)", () => {
    expect(eventDetailKo(rally)).toBe("5만 명 · 태평로");
    expect(eventDetailKo(loop)).toBe("5만 명 · 세종대로");
    if (!seg1) throw new Error("마라톤 1구간 없음");
    expect(eventDetailKo(seg1)).toBe("");
    // 기록된 공지 후보의 reported_people: 50,000(11/7 r01·r04) · 5,000(r06) · 200·400(11/9)
    expect([50000, 5000, 200, 400].map(peopleKo)).toEqual(["5만 명", "5,000명", "200명", "400명"]);
  });

  it("멈춤 경고 (T7.13) — 운영 기록의 TOPIS 돌발 수신 19:24:45: 기록 때(2분 뒤)·30분 정각은 없음, 넘으면 'N분째·시간째·일째', 받은 적 없으면 없음", () => {
    const prod = recorded("closure_events_prod_1107_1530"); // 운영 GET 2026-11-09 19:27:07
    const asOf = recordedEvents("closure_events_prod_1107_1530").data_as_of;
    const at = Date.parse(asOf.topis_incident ?? ""); // 2026-11-09T19:24:45+09:00
    expect(staleWarningKo(asOf, Date.parse(prod.fetched_at ?? ""))).toBeNull();
    expect(staleWarningKo(asOf, at + 30 * 60_000)).toBeNull();
    expect(staleWarningKo(asOf, at + 30 * 60_000 + 1_000)).toBe(
      "통제 정보가 30분째 갱신되지 않았어요",
    );
    expect(staleWarningKo(asOf, at + 125 * 60_000)).toBe("통제 정보가 2시간째 갱신되지 않았어요");
    expect(staleWarningKo(asOf, at + 3 * 24 * 60 * 60_000)).toBe(
      "통제 정보가 3일째 갱신되지 않았어요",
    );
    expect(staleWarningKo(recordedEvents().data_as_of, at)).toBeNull(); // topis_incident null
    expect(staleWarningKo(null, at)).toBeNull(); // 사건 응답 전
  });

  it("목록 위 기준 시각 — 경찰청 11/6 공지 · 마라톤 3/12 시각표, 실시간 돌발이 없으면 회색 경고", () => {
    expect(dataAsOfKo(res.data_as_of, Date.parse("2026-11-08T16:00:00+09:00"))).toEqual({
      text: "경찰청 11/6 공지 · 마라톤 3/12 시각표 기준",
      warning: "실시간 돌발(TOPIS)은 아직 받지 않아요",
    });
  });

  it("30분 넘게 안 바뀌면 오래된 것 — 경계는 30분", () => {
    const at = res.data_as_of.smpa ?? "";
    const t0 = Date.parse(at);
    expect(isStale(at, t0 + 30 * 60_000)).toBe(false);
    expect(isStale(at, t0 + 31 * 60_000)).toBe(true);
    expect(isStale(null, t0)).toBe(true);
  });
});

// T7.5 지금 서울 통제·사건 카드 — 사건 v2 기록(scripts/record_live_events.py)을 열어 확인한 창·출처·확신도
describe("사건 카드 문구 (T7.5)", () => {
  const a = recordedLive("closure_events_live_1107_1530");
  const m = recordedLive("closure_events_live_0315_0745");
  const n = recordedLive("closure_events_live_1109_1330");
  const ev = (x: typeof a, id: string) => eventById(x.body.events, id);

  it("남은 시간 — 예정은 'N시간 M분 뒤 시작', 시작했는데 근거 없으면 '시작 · 확인 전', 통제 중은 해제 예정", () => {
    expect(remainKo(ev(a, "a1199bc3db1d"), a.atMs)).toBe("30분 뒤 시작"); // r06 16:00, 15:30 기준
    expect(remainKo(ev(m, "e1d0e06932a8"), m.atMs)).toBe("1시간 27분 뒤 시작"); // 10구간 09:12
    expect(remainKo(ev(m, "5b1db12805d0"), m.atMs)).toBe("1시간 15분 뒤 시작"); // 9구간 09:00
    expect(remainKo(ev(a, "be5f89a4ebf3"), a.atMs)).toBe("12:00 시작 · 확인 전"); // r01 공지뿐
    expect(remainKo(ev(m, "adaea2f4cc02"), m.atMs)).toBe("08:08 해제 예정"); // 1구간 통제 중
    expect(remainKo(ev(n, "1deaa20a0218"), n.atMs)).toBe("13:00 해제"); // 하나증권 r01 해제
  });

  it("출처 — 경찰청 공지·TOPIS 공지·TOPIS 통제지도·TOPIS 돌발·마라톤 시간표", () => {
    expect(sourceKo(ev(a, "2e930ec6deeb"))).toBe("경찰청 공지");
    expect(sourceKo(ev(a, "3c408a6e5e4a"))).toBe("TOPIS 공지"); // 6300
    expect(sourceKo(ev(n, "ccaa9980c6ac"))).toBe("TOPIS 통제지도"); // notice_id topismap-1109233
    expect(sourceKo(ev(a, "159e13bfe71a"))).toBe("TOPIS 돌발");
    expect(sourceKo(ev(m, "adaea2f4cc02"))).toBe("마라톤 시간표");
  });

  it("확신도 문구 (T7.14) — 3/15 마라톤 높음 · 11/9 국회대로 TOPIS 돌발 높음 · 11/9 하나증권 행진(공지 0.75) 보통 · 교보빌딩 정문 앞(unknown 0.45) 낮음", () => {
    expect(CONFIDENCE_KO).toEqual({ high: "높음", mid: "보통", low: "낮음" });
    expect(confidenceKo(ev(m, "adaea2f4cc02").confidence)).toBe("높음"); // 1구간 시각표 0.9
    expect(confidenceKo(ev(n, "37d5497077a4").confidence)).toBe("높음"); // 돌발 국회대로 0.9, 통제 중
    // 후보 배치 candidates/notice/20261108T162420 — 문장 공지 11/9 r01(PDF 로 읽으면 0.85)
    const hana = recordedCandidate("notice/20261108T162420", "smpa-20261109-r01-i1-seg1");
    expect([hana.confidence, hana.impact, hana.status_hint]).toEqual([0.75, "blocks", "scheduled"]);
    expect(confidenceKo(hana.confidence)).toBe("보통");
    // 파서 기록 11/8 3행 — 점유 표현 없는 지점 집회. 리졸버가 '교보빌딩'을 종로에서 못 찾아 후보가 안 된다
    const [kyobo] = recordedNoticeItems("smpa-20261108-r03-u202611061800");
    expect([kyobo?.confidence, kyobo?.impact, kyobo?.points[0]?.name]).toEqual([
      0.45,
      "unknown",
      "교보빌딩 정문 앞",
    ]);
    expect(confidenceKo(kyobo?.confidence ?? 1)).toBe("낮음");
  });

  it("확신도 3단계 — 0.8 이상 높음, 0.7 이상 보통, 그 아래 낮음", () => {
    expect(confidenceKo(ev(a, "159e13bfe71a").confidence)).toBe("높음"); // 돌발 0.9
    expect(confidenceKo(ev(n, "ccaa9980c6ac").confidence)).toBe("높음"); // 통제지도 0.85
    expect(confidenceKo(ev(a, "2e930ec6deeb").confidence)).toBe("보통"); // r04 0.75
    expect(confidenceKo(ev(a, "3f036e3f24e0").confidence)).toBe("낮음"); // r05 0.65
  });

  it("배지 — 카드는 상태(곧 시작·확인 전 구분), 행은 남은 시간(통제 중 'N분 뒤 해제')", () => {
    expect(kindBadgeKo(ev(n, "ccaa9980c6ac"), n.atMs)).toBe("통제 중");
    expect(kindBadgeKo(ev(a, "a1199bc3db1d"), a.atMs)).toBe("곧 시작"); // 16:00, 30분 뒤
    expect(kindBadgeKo(ev(a, "be5f89a4ebf3"), a.atMs)).toBe("확인 전"); // 12:00 시작, 공지뿐
    expect(kindBadgeKo(ev(m, "e1d0e06932a8"), m.atMs)).toBe("예정"); // 09:12, 87분 뒤
    expect(kindBadgeKo(ev(n, "1deaa20a0218"), n.atMs)).toBe("해제");
    expect(rowBadgeKo(ev(m, "adaea2f4cc02"), m.atMs)).toBe("23분 뒤 해제"); // 1구간 08:08
    expect(rowBadgeKo(ev(m, "e1d0e06932a8"), m.atMs)).toBe("1시간 27분 뒤 시작");
    expect(rowBadgeKo(ev(a, "be5f89a4ebf3"), a.atMs)).toBe("확인 전");
  });

  it("해제 예정 뒤 30분은 정리 중 (태우 11/10) — BE 는 끝 + 30분에야 released: 3/15 1구간 끝 08:08", () => {
    const end = "2026-03-15T08:08:00+09:00"; // 사건 v2 3/15 07:45 adaea2f4cc02 window.end
    expect(untilKo(end, "2026-03-15T07:45:00+09:00")).toBe("23분 뒤 해제");
    expect(untilKo(end, "2026-03-15T08:08:00+09:00")).toBe("정리 중 · 08:38까지");
    expect(untilKo(end, "2026-03-15T08:37:00+09:00")).toBe("정리 중 · 08:38까지");
    expect(untilKo(end, "2026-03-15T08:38:00+09:00")).toBe("해제됨"); // 끝 + 30분 = released
    const seg1 = ev(m, "adaea2f4cc02"); // 07:45 기록 — confirmed
    expect(remainKo(seg1, m.atMs)).toBe("08:08 해제 예정");
    expect(remainKo(seg1, Date.parse("2026-03-15T08:20:00+09:00"))).toBe("08:38까지 정리 중");
    expect(rowBadgeKo(seg1, Date.parse("2026-03-15T08:20:00+09:00"))).toBe("정리 중 · 08:38까지");
    expect(GRACE_NOTE_KO).toBe("해제 예정 시각 뒤 30분은 현장 정리로 막힌 걸로 봐요");
  });

  it("시트 제목 — 지금이면 '지금 서울 통제', 아니면 '서울 통제'(날짜·시각은 기준 줄, T7.12)", () => {
    expect(liveTitleKo(true)).toBe("지금 서울 통제");
    expect(liveTitleKo(false)).toBe("서울 통제");
  });

  it("시트 목록 배지 (T7.12) — 지난 통제는 날짜, 다른 날 시작하는 다가오는 통제는 '예정'(날짜는 묶음 머리)", () => {
    const c = recordedLive("closure_events_catalog_1108_1200"); // 넓은 창 11/8 12:00
    expect(sheetBadgeKo(ev(c, "a1199bc3db1d"), c.atMs)).toBe("11월 7일"); // r06 11/7 16:00–19:00 해제
    expect(sheetBadgeKo(ev(c, "1deaa20a0218"), c.atMs)).toBe("예정"); // 하나증권 11/9 10:30
    expect(sheetBadgeKo(ev(m, "e1d0e06932a8"), m.atMs)).toBe("1시간 27분 뒤 시작"); // 10구간 같은 날 09:12
    expect(sheetBadgeKo(ev(m, "adaea2f4cc02"), m.atMs)).toBe("23분 뒤 해제"); // 1구간 08:08
  });

  it("긴 경로는 처음·끝만(경유 3곳부터), 도로는 셋까지 '외 N곳' — 카드에는 지나는 곳 전부 (T7.3 숙제)", () => {
    const march = ev(n, "ccaa9980c6ac"); // 국회의사당앞 → (경유 9) → 효자동삼거리, 도로 10
    expect(eventTitleKo(march)).toBe("국회의사당앞 → 효자동삼거리 행진");
    expect(eventDetailKo(march)).toBe("국회대로·여의서로·여의대로 외 7곳");
    expect(longRouteKo(march)).toBe(
      "국회의사당앞 → 서강대교남단 → 마포대교남단 → 마포대교북단 → 아현교차로 → 충정로사거리 → " +
        "서대문역 → 세종대로사거리 → 광화문 → 정부서울청사 → 효자동삼거리",
    );
    expect(longRouteKo(ev(a, "be5f89a4ebf3"))).toBeNull(); // 경유 1곳(동화면세점 고리)은 제목 그대로
    expect(eventTitleKo(ev(a, "be5f89a4ebf3"))).toBe(
      "동화면세점 앞 → 종로1가사거리 → 동화면세점 앞 행진",
    );
  });
});

describe("시트 세 묶음 문구 (T7.12)", () => {
  it("다가오는 통제 날짜 머리 — 오늘·내일, 그 밖은 '11월 9일 (월)' (기준 시각의 KST 날짜로)", () => {
    const at1108 = Date.parse("2026-11-08T12:00:00+09:00"); // 넓은 창 기록 11/8 12:00
    const at1107 = Date.parse("2026-11-07T15:30:00+09:00"); // 넓은 창 기록 11/7 15:30
    expect(dayLabelKo("2026-11-09", at1108)).toBe("내일");
    expect(dayLabelKo("2026-11-08", at1108)).toBe("오늘");
    expect(dayLabelKo("2026-11-09", at1107)).toBe("11월 9일 (월)");
  });
  it("지금이 아닐 때 시트 위 — '11월 7일 15:00 기준', 빈 지금 묶음 문구", () => {
    expect(bannerKo("2026-11-07T15:00:00+09:00")).toBe("11월 7일 15:00 기준"); // 경찰청 r04 시작
    expect(nowEmptyKo(true)).toBe("지금 서울에 걸린 통제가 없어요");
    expect(nowEmptyKo(false)).toBe("이 시각 서울에 걸린 통제가 없어요");
  });
});
