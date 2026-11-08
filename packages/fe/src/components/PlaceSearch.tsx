"use client";

import { useEffect, useState } from "react";
import { placeLngLat } from "../api/naruApiClient";
import { searchStatusKo } from "../i18n/ko";
import { useNaruApi } from "../state/ApiProvider";
import { useClosures } from "../state/ClosureProvider";
import { useRouteDispatch, type OdField } from "../state/RouteProvider";
import type { Place } from "../types/contracts";
import styles from "./PlaceSearch.module.css";

// 장소 검색 (T5.8, INTERFACE §7.1) — 2글자 이상, 300ms 쉬면 /api/geocode/search. near = 지도 가운데.
// 홈 검색창은 결과마다 '출발'·'도착', 출발·도착 칸 입력은 줄을 누르면 그 칸에
export const SEARCH_MIN_CHARS = 2;
export const SEARCH_DEBOUNCE_MS = 300;

/** 지도 bbox("w,s,e,n") 가운데 → near "lat,lng" 소수 4자리. BE 가 다시 2자리(약 1 km)로 맞춘다 */
export function nearOf(bbox: string): string | undefined {
  const nums = bbox.split(",").map(Number);
  const [w, s, e, n] = nums;
  if (nums.length !== 4 || w === undefined || s === undefined || e === undefined) return undefined;
  if (n === undefined || !nums.every(Number.isFinite)) return undefined;
  return `${((s + n) / 2).toFixed(4)},${((w + e) / 2).toFixed(4)}`;
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
  which,
  onChoose,
}: {
  places: readonly Place[];
  /** 칸 입력이면 그 칸, 홈 검색창이면 null(줄마다 출발·도착) */
  which: OdField | null;
  onChoose: (place: Place, which: OdField) => void;
}) {
  return (
    <ul className={styles.list} aria-label="검색 결과">
      {places.map((p) => (
        <li key={p.id} className={styles.row}>
          {which ? (
            <button
              type="button"
              className={styles.pick}
              aria-label={`${p.name} ${p.address}`}
              onClick={() => onChoose(p, which)}
            >
              <b>{p.name}</b>
              <small>{p.address}</small>
            </button>
          ) : (
            <>
              <div className={styles.text}>
                <b>{p.name}</b>
                <small>{p.address}</small>
              </div>
              <button
                type="button"
                className={styles.act}
                aria-label={`${p.name} 출발`}
                onClick={() => onChoose(p, "from")}
              >
                출발
              </button>
              <button
                type="button"
                className={styles.act}
                aria-label={`${p.name} 도착`}
                onClick={() => onChoose(p, "to")}
              >
                도착
              </button>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}

/** 검색 결과 칸 — 상태 한 줄 또는 목록, 닫기. 고르면 RouteProvider 의 choose */
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
  const choose = (place: Place, w: OdField) => {
    const point = placeLngLat(place);
    if (point) dispatch({ type: "choose", which: w, point, name: place.name });
  };
  const places = result.status === "done" ? result.places : [];
  return (
    <div className={styles.results}>
      {places.length > 0 ? (
        <PlaceList places={places} which={which} onChoose={choose} />
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
