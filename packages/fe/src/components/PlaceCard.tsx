"use client";

import { PLACE_KO } from "../i18n/ko";
import { useRoute, useRouteDispatch, type OdField } from "../state/RouteProvider";
import { useSavedPlaces } from "../state/savedPlaces";
import styles from "./PlaceCard.module.css";

// 검색한 장소 카드 (T7.14, 네이버지도·카카오맵처럼) — 이름 · 도로명 주소 · [출발] [도착] [☆ 저장].
// 출발·도착을 누르면 길찾기(그 칸), 닫으면 지도 핀도 사라진다. 저장은 이 기기에만(localStorage)
export function PlaceCard() {
  const { place } = useRoute();
  const dispatch = useRouteDispatch();
  const { saved, toggle } = useSavedPlaces();
  if (!place) return null;
  const isSaved = saved.some((p) => p.id === place.id);
  const choose = (which: OdField) =>
    dispatch({ type: "choose", which, point: place.point, name: place.name });
  return (
    <article className={styles.card} aria-label={place.name}>
      <div className={styles.top}>
        <h2 className={styles.name}>{place.name}</h2>
        <button
          type="button"
          className={styles.close}
          aria-label={PLACE_KO.close}
          onClick={() => dispatch({ type: "place", place: null })}
        >
          ×
        </button>
      </div>
      <p className={styles.address}>{place.address}</p>
      <div className={styles.actions}>
        <button type="button" className={styles.primary} onClick={() => choose("from")}>
          {PLACE_KO.from}
        </button>
        <button type="button" className={styles.primary} onClick={() => choose("to")}>
          {PLACE_KO.to}
        </button>
        <button
          type="button"
          className={styles.save}
          aria-pressed={isSaved}
          onClick={() => toggle(place)}
        >
          {isSaved ? PLACE_KO.saved : PLACE_KO.save}
        </button>
      </div>
    </article>
  );
}
