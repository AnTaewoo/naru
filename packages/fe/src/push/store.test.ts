// 알림 스토어 순수 부분 (T7.10) — 관심 지역 매칭·localStorage 저장. 관심 지역은 기록 watch_areas(실제 앱 응답)
import { describe, expect, it } from "vitest";
import { recorded } from "../test/recorded";
import type { WatchAreasResponse } from "../types/contracts";
import {
  ENDPOINT_KEY,
  LABEL_KEY,
  readEndpoint,
  readLabels,
  watchedArea,
  writeEndpoint,
  writeLabels,
} from "./store";

const { areas } = recorded("watch_areas").body as WatchAreasResponse;
const KYOBO: [number, number] = [126.9779039768265, 37.5709686446227]; // 카카오 점 (요청 좌표)

describe("push store (T7.10)", () => {
  it("저장 관심 지역이 이 점(사건 중심)과 같으면 ★ — 서버는 소수 7자리, 마지막 위치는 안 본다", () => {
    const saved = areas.find((a) => a.kind === "saved");
    expect(saved).toBeDefined();
    expect(watchedArea(areas, KYOBO)?.id).toBe(saved?.id);
    expect(watchedArea(areas, [126.976542945622, 37.5650416322942])).toBeNull(); // 대한문은 last_seen
    expect(watchedArea([], KYOBO)).toBeNull();
  });

  it("구독 endpoint·라벨은 이 브라우저 localStorage — 깨진 값은 없는 것으로", () => {
    localStorage.removeItem(ENDPOINT_KEY);
    expect(readEndpoint(localStorage)).toBeNull();
    writeEndpoint("https://push.example/abc", localStorage);
    expect(readEndpoint(localStorage)).toBe("https://push.example/abc");
    localStorage.setItem(ENDPOINT_KEY, '{"endpoint":"http://x"}');
    expect(readEndpoint(localStorage)).toBeNull();
    writeEndpoint(null, localStorage);
    expect(localStorage.getItem(ENDPOINT_KEY)).toBeNull();
    writeLabels({ "55": "동화면세점 앞 → 종로1가사거리 → 동화면세점 앞 행진" }, localStorage);
    expect(readLabels(localStorage)["55"]).toContain("동화면세점");
    localStorage.setItem(LABEL_KEY, "[1,2]");
    expect(readLabels(localStorage)).toEqual({});
    expect(readEndpoint(null)).toBeNull();
  });
});
