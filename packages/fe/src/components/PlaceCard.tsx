"use client";

import { useEffect, useState } from "react";
import { PLACE_KO, PUSH_KO } from "../i18n/ko";
import { usePush } from "../push/usePush";
import { useRoute, useRouteDispatch, type OdField } from "../state/RouteProvider";
import { useSavedPlaces } from "../state/savedPlaces";
import styles from "./PlaceCard.module.css";

// 검색한 장소 카드 (T7.14, 네이버지도·카카오맵처럼) — 이름 · 도로명 주소 · [출발] [도착] [☆ 저장] 그리고
// [☆ 이 근처 알림 받기]. 출발·도착을 누르면 길찾기(그 칸), 닫으면 지도 핀도 사라진다. 저장은 이 기기에만(localStorage).
// 알림(T7.10, 태우 11/11 — 사건이 생긴 뒤에야 누를 수 있는 사건 카드 ☆ 대신 원하는 장소에서): 이 자리 반경
// 500 m 를 저장 관심 지역으로. 이미 있으면 ★, 누르면 뺀다. 알림을 못 켜는 브라우저면 까닭 한 줄
export function PlaceCard() {
  const { place } = useRoute();
  const dispatch = useRouteDispatch();
  const { saved, toggle } = useSavedPlaces();
  const push = usePush();
  const [note, setNote] = useState<string | null>(null);
  useEffect(() => setNote(null), [place?.id]);
  if (!place) return null;
  const isSaved = saved.some((p) => p.id === place.id);
  const choose = (which: OdField) =>
    dispatch({ type: "choose", which, point: place.point, name: place.name });
  const watched = push.watchedArea(place.point);
  const watchNote =
    note ??
    (push.error === "limit" ? PUSH_KO.limit : push.error === "failed" ? PUSH_KO.failed : null);
  const toggleWatch = () => {
    if (watched) return push.unwatch(watched.id);
    if (push.support === "ios_install") return setNote(PUSH_KO.iosInstall);
    if (push.support === "denied") return setNote(PUSH_KO.denied);
    if (push.support === "unsupported") return setNote(PUSH_KO.unsupported);
    push.watch(place.point, place.name);
  };
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
      <button
        type="button"
        className={styles.watch}
        aria-pressed={watched !== null}
        disabled={push.busy}
        onClick={toggleWatch}
      >
        {watched ? PUSH_KO.watching : PUSH_KO.watch}
      </button>
      {watchNote && (
        <p className={styles.note} role="status">
          {watchNote}
        </p>
      )}
    </article>
  );
}
