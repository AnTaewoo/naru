// 통제 제보 상태 (T7.15, INTERFACE §8) — 기록 응답(scripts/record_live_events.py 가 naru_test 의 실제 앱에서
// 받은 것)으로. 위치는 기록 질의 그대로(카카오 '광화문교보빌딩' 점), 네트워크 없음
import { describe, expect, it } from "vitest";
import { NaruApiError, parseNearestCrosswalk } from "../api/naruApiClient";
import { recorded } from "../test/recorded";
import type { ErrorBody } from "../types/contracts";
import {
  DEVICE_KEY,
  crosswalkOf,
  deviceToken,
  failureOf,
  fieldModeFromLocation,
  reportReducer,
} from "./report";

const KYOBO: [number, number] = [126.9779039768265, 37.5709686446227];
const kyoboCw = crosswalkOf(parseNearestCrosswalk(recorded("report_nearest_kyobo").body));

describe("통제 제보 상태 (T7.15)", () => {
  it("위치 → 최근접(기록: 교보생명 71 m) → 막혔어요 → 보냄. 횡단보도를 찾으면 위치 좌표는 버린다", () => {
    let s = reportReducer(null, { type: "start", field: false });
    expect(s).toMatchObject({ phase: "locating", field: false, crosswalk: null });
    s = reportReducer(s, { type: "located", point: KYOBO, accuracyM: 14 });
    expect(s).toMatchObject({ phase: "finding", point: KYOBO, accuracyM: 14 });
    expect(kyoboCw).toEqual({
      id: "06-0000051345",
      name: "교보생명",
      district: "종로구",
      point: [126.97768829792257, 37.571585764131775],
      distanceM: 71,
    });
    s = reportReducer(s, { type: "found", crosswalk: kyoboCw });
    expect(s).toMatchObject({ phase: "ready", point: null, crosswalk: kyoboCw });
    s = reportReducer(s, { type: "send", value: "blocked" });
    expect(s).toMatchObject({ phase: "sending", sent: "blocked" });
    expect(reportReducer(s, { type: "send", value: "open" })).toBe(s); // 보내는 중엔 무시
    s = reportReducer(s, { type: "sent" });
    expect(s?.phase).toBe("sent");
    expect(reportReducer(s, { type: "close" })).toBeNull();
  });

  it("서울 밖(기록: 성남 → null)은 none, 1000 m 보다 흐리면 inaccurate, 같은 기기 다시(기록 429)는 too_many", () => {
    const finding = reportReducer(reportReducer(null, { type: "start", field: true }), {
      type: "located",
      point: KYOBO,
      accuracyM: 14,
    });
    const none = crosswalkOf(parseNearestCrosswalk(recorded("report_nearest_none").body));
    expect(none).toBeNull();
    expect(reportReducer(finding, { type: "found", crosswalk: none })).toMatchObject({
      phase: "error",
      failure: "none",
      point: null,
      field: true,
    });
    const blurry = reportReducer(reportReducer(null, { type: "start", field: false }), {
      type: "located",
      point: KYOBO,
      accuracyM: 1001,
    });
    expect(blurry).toMatchObject({ phase: "error", failure: "inaccurate", point: null });
    const r = recorded("report_too_many");
    expect(r.status).toBe(429);
    expect(failureOf(new NaruApiError(r.status, r.body as ErrorBody))).toBe("too_many");
    expect(failureOf(new TypeError("Failed to fetch"))).toBe("failed");
  });

  it("다시 하기 — 보내다 실패(failed)면 같은 횡단보도로, 그 밖은 위치부터", () => {
    const ready = reportReducer(
      reportReducer(reportReducer(null, { type: "start", field: false }), {
        type: "located",
        point: KYOBO,
        accuracyM: 14,
      }),
      { type: "found", crosswalk: kyoboCw },
    );
    const sending = reportReducer(ready, { type: "send", value: "open" });
    const failed = reportReducer(sending, { type: "fail", failure: "failed" });
    expect(reportReducer(failed, { type: "retry" })).toMatchObject({
      phase: "ready",
      crosswalk: kyoboCw,
      failure: null,
    });
    const tooMany = reportReducer(sending, { type: "fail", failure: "too_many" });
    expect(reportReducer(tooMany, { type: "retry" })).toMatchObject({
      phase: "locating",
      crosswalk: null,
    });
  });

  it("기기 토큰은 이 브라우저에 한 번 만들어 둔다 (localStorage naru.device.v1)", () => {
    localStorage.removeItem(DEVICE_KEY);
    const a = deviceToken(localStorage);
    expect(a).toMatch(/^[A-Za-z0-9-]{16,64}$/);
    expect(localStorage.getItem(DEVICE_KEY)).toBe(a);
    expect(deviceToken(localStorage)).toBe(a);
    localStorage.setItem(DEVICE_KEY, "깨진 값");
    expect(deviceToken(localStorage)).not.toBe("깨진 값");
    // 저장소가 막혀도(사생활 모드) 이 화면 동안은 같은 값
    expect(deviceToken(null)).toMatch(/^[A-Za-z0-9-]{16,64}$/);
    expect(deviceToken(null)).toBe(deviceToken(null));
  });

  it("?mode=field 면 현장 검증 제보", () => {
    expect(fieldModeFromLocation("?mode=field&t=2026-11-14T13:00:00%2B09:00")).toBe(true);
    expect(fieldModeFromLocation("")).toBe(false);
    expect(fieldModeFromLocation("?mode=walk")).toBe(false);
  });
});
