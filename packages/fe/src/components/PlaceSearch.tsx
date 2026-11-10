"use client";

import { useEffect, useState } from "react";
import { placeLngLat } from "../api/naruApiClient";
import { PLACE_KO, distanceKo, searchStatusKo } from "../i18n/ko";
import { bboxCenter, distanceM } from "../map/geo";
import type { LngLat } from "../map/layers/routeLayer";
import { useNaruApi } from "../state/ApiProvider";
import { useClosures } from "../state/ClosureProvider";
import { placePick, useRouteDispatch, type OdField, type PlacePick } from "../state/RouteProvider";
import type { Place } from "../types/contracts";
import styles from "./PlaceSearch.module.css";

// 장소 검색 (T5.8, INTERFACE §7.1) — 2글자 이상, 300ms 쉬면 /api/geocode/search. near = 지도 가운데.
// 줄마다 이름·주소·지도 가운데부터 거리(T7.14). 홈 검색창은 줄을 누르면 그 장소(지도 이동·핀·장소 카드),
// 출발·도착 칸 입력은 그 칸에
export const SEARCH_MIN_CHARS = 2;
export const SEARCH_DEBOUNCE_MS = 300;

/** 지도 bbox("w,s,e,n") 가운데 → near "lat,lng" 소수 4자리. BE 가 다시 2자리(약 1 km)로 맞춘다 */
export function nearOf(bbox: string): string | undefined {
  const c = bboxCenter(bbox);
  return c ? `${c[1].toFixed(4)},${c[0].toFixed(4)}` : undefined;
}

/** 지도 가운데부터 거리 "387m" (T7.14) — 가운데를 모르면 null */
function farKo(center: LngLat | null, point: LngLat | null): string | null {
  return center && point ? distanceKo(distanceM(center, point)) : null;
}

type SearchResult =
  { status: "short" | "loading" | "error" } | { status: "done"; places: readonly Place[] };

/** 검색어가 바뀌면 300ms 뒤 한 번 (이전 요청은 Abort). 지금 검색어의 결과가 오기 전엔 loading */
function usePlaceSearch(query: string): SearchResult {
  const api = useNaruApi();
  const near = nearOf(useClosures().bbox);
  const q = query.trim();
  const [got, setGot] = useState<{ q: string; result: SearchResult } | null>(null);
  useEffect(() => {
    if (q.length < SEARCH_MIN_CHARS) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api
        .geocodeSearch({ q, near }, controller.signal)
        .then((r) => setGot({ q, result: { status: "done", places: r.places } }))
        .catch(() => {
          if (!controller.signal.aborted) setGot({ q, result: { status: "error" } });
        });
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [api, q, near]);
  if (q.length < SEARCH_MIN_CHARS) return { status: "short" };
  return got?.q === q ? got.result : { status: "loading" };
}

export function PlaceList({
  places,
  center,
  onChoose,
}: {
  places: readonly Place[];
  /** 지도 가운데 [lng, lat] — 줄마다 거리 (T7.14) */
  center: LngLat | null;
  onChoose: (place: Place) => void;
}) {
  return (
    <ul className={styles.list} aria-label="검색 결과">
      {places.map((p) => {
        const far = farKo(center, placeLngLat(p));
        return (
          <li key={p.id} className={styles.row}>
            <button
              type="button"
              className={styles.pick}
              aria-label={`${p.name} ${p.address}`}
              onClick={() => onChoose(p)}
            >
              <b>{p.name}</b>
              <small>{p.address}</small>
            </button>
            {far && <em className={styles.far}>{far}</em>}
          </li>
        );
      })}
    </ul>
  );
}

/** 홈 검색칸이 비었을 때 저장한 장소 (T7.14) — 누르면 검색 결과처럼 그 장소 */
export function SavedList({
  saved,
  center,
  onChoose,
}: {
  saved: readonly PlacePick[];
  center: LngLat | null;
  onChoose: (place: PlacePick) => void;
}) {
  return (
    <div className={styles.results}>
      <p className={styles.head}>{PLACE_KO.savedHead}</p>
      <ul className={styles.list} aria-label={PLACE_KO.savedHead}>
        {saved.map((p) => {
          const far = farKo(center, p.point);
          return (
            <li key={p.id} className={styles.row}>
              <button
                type="button"
                className={styles.pick}
                aria-label={`${p.name} ${p.address}`}
                onPointerDown={(e) => e.preventDefault()} // 검색칸 포커스를 잃기 전에 누른다
                onClick={() => onChoose(p)}
              >
                <b>{p.name}</b>
                <small>{p.address}</small>
              </button>
              {far && <em className={styles.far}>{far}</em>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** 검색 결과 칸 — 상태 한 줄 또는 목록, 닫기. 고르면 칸이면 choose, 홈이면 place (T7.14) */
export function SearchResults({
  query,
  which,
  onClose,
}: {
  query: string;
  which: OdField | null;
  onClose: () => void;
}) {
  const result = usePlaceSearch(query);
  const dispatch = useRouteDispatch();
  const center = bboxCenter(useClosures().bbox);
  // 칸 입력이면 그 칸에, 홈이면 그 장소(지도 이동·핀·장소 카드) — 결과 칸은 닫는다 (T7.14)
  const choose = (place: Place) => {
    const pick = placePick(place);
    if (!pick) return;
    if (which) {
      dispatch({ type: "choose", which, point: pick.point, name: pick.name });
    } else {
      dispatch({ type: "place", place: pick });
      onClose();
    }
  };
  const places = result.status === "done" ? result.places : [];
  return (
    <div className={styles.results}>
      {places.length > 0 ? (
        <PlaceList places={places} center={center} onChoose={choose} />
      ) : (
        <p className={styles.status} role="status">
          {searchStatusKo(result.status === "done" ? "empty" : result.status, which !== null)}
        </p>
      )}
      <div className={styles.foot}>
        <button type="button" className={styles.close} onClick={onClose}>
          닫기
        </button>
      </div>
    </div>
  );
}
