// 통제 목록 문구 (T5.9, ADR-012) — 제목·둘째 줄·인원·기준 시각은 FE 템플릿. 입력은 recorded
// naru_api/closure_events.json(v0.12 재기록): 공지 r04·r01 의 summary, 코스는 summary 없음, data_as_of
import { describe, expect, it } from "vitest";
import { recordedEvents } from "../test/recorded";
import type { ClosureEvent } from "../types/contracts";
import { dataAsOfKo, eventDetailKo, eventTitleKo, isStale, peopleKo } from "./ko";

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
