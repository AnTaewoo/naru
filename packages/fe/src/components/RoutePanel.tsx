"use client";

import { useEffect, useRef, useState } from "react";
import {
  LOCATING_KO,
  MY_LOCATION_KO,
  SEARCH_PLACEHOLDER_KO,
  SELECTED_PLACE_KO,
  fieldSearchPlaceholderKo,
  locateButtonKo,
  odHintKo,
} from "../i18n/ko";
import { bboxCenter } from "../map/geo";
import type { LngLat } from "../map/layers/routeLayer";
import { useClosures } from "../state/ClosureProvider";
import {
  useRoute,
  useRouteDispatch,
  type OdField,
  type PlaceName,
  type PlacePick,
} from "../state/RouteProvider";
import { readSaved } from "../state/savedPlaces";
import { SavedList, SearchResults } from "./PlaceSearch";
import styles from "./RoutePanel.module.css";

// 시안 01 검색창 → 홈은 장소 검색(결과마다 출발·도착) + 길찾기 버튼. 길찾기를 켜면 시안 02 rpanel
// (뒤로·출발/도착·내 위치·바꾸기·탭). 칸을 누르면 그 칸이 검색 입력칸이고, 그동안 지도를 누르면 그 칸에
// (T5.8). 좌표는 화면에 쓰지 않는다 — 장소 이름·주소, 모르면 "선택한 위치". 경로 종류가 하나("가장
// 빠른 길")라 탭 줄은 숨긴다 — 분은 아래 경로 카드에 있다 (T5.10)
const OD_NAME = { from: "출발", to: "도착" } as const;

function samePoint(a: LngLat, b: LngLat | null): boolean {
  return b !== null && a[0] === b[0] && a[1] === b[1];
}

/** 칸에 쓰는 글 — 찾는 중 / 비었으면 지도를 누르라고 / 내 위치 / 장소 이름·주소 / 모르면 "선택한 위치" */
function fieldText(
  which: OdField,
  p: LngLat | null,
  locating: OdField | null,
  mine: LngLat | null,
  name: PlaceName | null,
): string {
  if (locating === which) return LOCATING_KO;
  if (!p) return odHintKo(which);
  if (samePoint(p, mine)) return MY_LOCATION_KO;
  return name?.text && samePoint(name.point, p) ? name.text : SELECTED_PLACE_KO;
}

function Field({ which, text, filled }: { which: OdField; text: string; filled: boolean }) {
  const dispatch = useRouteDispatch();
  const name = OD_NAME[which];
  return (
    <button
      type="button"
      className={styles.f}
      aria-label={`${name} ${text}`}
      title={`누르면 ${name}을 검색하거나 지도로 다시 고른다`}
      onClick={() => dispatch({ type: "edit", which })}
    >
      <small>{name}</small>
      <span className={filled ? styles.v : styles.hint}>{text}</span>
    </button>
  );
}

/** 입력 중인 칸 — 열리면 바로 입력, Esc 는 닫기 */
function FieldInput({
  which,
  query,
  onQuery,
}: {
  which: OdField;
  query: string;
  onQuery: (q: string) => void;
}) {
  const dispatch = useRouteDispatch();
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);
  return (
    <input
      ref={ref}
      type="search"
      className={styles.input}
      aria-label={`${OD_NAME[which]} 검색`}
      placeholder={fieldSearchPlaceholderKo(which)}
      value={query}
      autoComplete="off"
      enterKeyHint="search"
      onChange={(e) => onQuery(e.target.value)}
      onKeyDown={(e) => {
        if (e.key === "Escape") dispatch({ type: "edit", which: null });
      }}
    />
  );
}

/** 칸 옆 '내 위치' — 누르면 그 칸을 내 위치로 (찾는 동안 aria-busy) */
function LocateButton({ which, busy }: { which: OdField; busy: boolean }) {
  const dispatch = useRouteDispatch();
  return (
    <button
      type="button"
      className={
        busy ? `${styles.icon} ${styles.loc} ${styles.busy}` : `${styles.icon} ${styles.loc}`
      }
      aria-label={locateButtonKo(which)}
      aria-busy={busy}
      title={locateButtonKo(which)}
      onClick={() => dispatch({ type: "locate", which })}
    >
      <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden>
        <circle cx="10" cy="10" r="5.5" stroke="currentColor" strokeWidth="1.8" fill="none" />
        <circle cx="10" cy="10" r="2.2" fill="currentColor" />
        <path
          d="M10 1.5v3M10 15.5v3M1.5 10h3M15.5 10h3"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
      </svg>
    </button>
  );
}

/** 홈 — 장소·주소 검색(줄을 누르면 그 장소: 지도 이동·핀·장소 카드, T7.14) + 길찾기. 칸이 비었는데 누르고
 * 있으면 저장한 장소 */
function HomeSearch() {
  const dispatch = useRouteDispatch();
  const { place } = useRoute();
  const center = bboxCenter(useClosures().bbox);
  const [query, setQuery] = useState("");
  const [saved, setSaved] = useState<PlacePick[] | null>(null);
  // 다른 곳을 검색하면 검색한 장소(핀·카드)는 사라진다
  const type = (q: string) => {
    setQuery(q);
    if (place && q.trim() !== "") dispatch({ type: "place", place: null });
  };
  return (
    <div className={styles.home}>
      <div className={styles.entry}>
        <input
          type="search"
          className={styles.search}
          aria-label={SEARCH_PLACEHOLDER_KO}
          placeholder={SEARCH_PLACEHOLDER_KO}
          value={query}
          autoComplete="off"
          enterKeyHint="search"
          onChange={(e) => type(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") setQuery("");
          }}
          onFocus={() => setSaved(readSaved(window.localStorage))}
          onBlur={() => setSaved(null)}
        />
        <button
          type="button"
          className={styles.go}
          aria-label="길찾기"
          title="지도에서 출발·도착을 골라 길찾기"
          onClick={() => dispatch({ type: "open" })}
        >
          <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden>
            <path
              d="M4 10h10m-4-4 4 4-4 4"
              stroke="#fff"
              strokeWidth="2"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      </div>
      {query.trim() !== "" && (
        <SearchResults query={query} which={null} onClose={() => setQuery("")} />
      )}
      {query.trim() === "" && saved && saved.length > 0 && (
        <SavedList
          saved={saved}
          center={center}
          onChoose={(p) => {
            dispatch({ type: "place", place: p });
            setSaved(null);
          }}
        />
      )}
    </div>
  );
}

export function RoutePanel() {
  const { active, from, to, locate, mine, names, editing } = useRoute();
  const dispatch = useRouteDispatch();
  // 입력 중인 칸의 검색어 — 칸이 바뀌면 빈 칸에서 시작
  const [search, setSearch] = useState<{ which: OdField | null; q: string }>({
    which: null,
    q: "",
  });
  if (!active) return <HomeSearch />;
  const query = search.which === editing ? search.q : "";
  const setQuery = (q: string) => setSearch({ which: editing, q });
  const locating = locate?.status === "locating" ? locate.which : null;
  const fromText = fieldText("from", from, locating, mine, names.from);
  const toText = fieldText("to", to, locating, mine, names.to);
  return (
    <section className={styles.panel} aria-label="출발·도착">
      <div className={styles.od}>
        <button
          type="button"
          className={styles.icon}
          aria-label="뒤로"
          onClick={() => dispatch({ type: "close" })}
        >
          <svg width="22" height="22" viewBox="0 0 22 22">
            <path
              d="M13 5 7 11l6 6"
              stroke="#222"
              strokeWidth="2.2"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        {editing === "from" ? (
          <FieldInput which="from" query={query} onQuery={setQuery} />
        ) : (
          <Field which="from" text={fromText} filled={from !== null && locating !== "from"} />
        )}
        <LocateButton which="from" busy={locating === "from"} />
        <button
          type="button"
          className={`${styles.icon} ${styles.swap}`}
          aria-label="출발·도착 바꾸기"
          disabled={!from || !to}
          onClick={() => dispatch({ type: "swap" })}
        >
          <svg width="22" height="22" viewBox="0 0 22 22">
            <path
              d="M7 5v12m0 0-3-3m3 3 3-3M15 17V5m0 0-3 3m3-3 3 3"
              stroke="#777"
              strokeWidth="1.8"
              fill="none"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
        <span aria-hidden />
        {editing === "to" ? (
          <FieldInput which="to" query={query} onQuery={setQuery} />
        ) : (
          <Field which="to" text={toText} filled={to !== null && locating !== "to"} />
        )}
        <LocateButton which="to" busy={locating === "to"} />
      </div>
      {editing && (
        <SearchResults
          query={query}
          which={editing}
          onClose={() => dispatch({ type: "edit", which: null })}
        />
      )}
    </section>
  );
}
