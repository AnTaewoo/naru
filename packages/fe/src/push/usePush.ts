"use client";

import { useCallback, useEffect, useSyncExternalStore } from "react";
import { NaruApiError, type NaruApiClient } from "../api/naruApiClient";
import { useNaruApi } from "../state/ApiProvider";
import type { WatchArea } from "../types/contracts";
import {
  WATCH_RADIUS_M,
  readEndpoint,
  readLabels,
  readStore,
  setStore,
  subscribeStore,
  watchedArea,
  writeEndpoint,
  writeLabels,
  type PushStore,
} from "./store";
import { isIOS, pushSupport, type PushEnv } from "./support";

// 알림 훅 (ADR-014 D — Provider 추가 없음, T7.7 → T7.10) — 마운트 뒤 브라우저 지원을 읽고 서비스워커(/sw.js)를
// 등록한다. 권한은 enable()(버튼) 에서만 묻고, 허용되면 VAPID 공개키로 pushManager.subscribe → POST /push/subscribe.
// 관심 지역은 서버(§9.3) — 사건 카드 ☆(watch)·목록 빼기(unwatch)·내 위치 켰을 때 last_seen(lastSeenFrom)
export const SW_URL = "/sw.js";

function readEnv(): PushEnv {
  const nav = window.navigator;
  const ios = isIOS(nav.userAgent, nav.platform, nav.maxTouchPoints);
  // jsdom(렌더 테스트)엔 matchMedia 가 없다
  const standalone =
    (nav as Navigator & { standalone?: boolean }).standalone === true ||
    (typeof window.matchMedia === "function" &&
      window.matchMedia("(display-mode: standalone)").matches);
  return {
    serviceWorker: "serviceWorker" in nav,
    pushManager: "PushManager" in window,
    notification: "Notification" in window,
    permission: "Notification" in window ? Notification.permission : null,
    ios,
    standalone,
  };
}

function keyBytes(b64url: string): Uint8Array {
  const pad = "=".repeat((4 - (b64url.length % 4)) % 4);
  const raw = atob(b64url.replace(/-/g, "+").replace(/_/g, "/") + pad);
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

/** 서버 구독 목록을 받아 스토어에 — 구독이 없어졌으면(404) endpoint 를 잊는다 */
async function refreshAreas(api: NaruApiClient, endpoint: string): Promise<void> {
  try {
    const { areas } = await api.watchAreas(endpoint);
    setStore({ endpoint, areas, labels: readLabels(), error: null });
  } catch (e) {
    if (e instanceof NaruApiError && e.status === 404) {
      writeEndpoint(null);
      setStore({ endpoint: null, areas: [] });
    }
  }
}

/** 브라우저 구독을 만들거나(이미 있으면 그대로) 서버에 올린다 → endpoint */
async function ensureSubscribed(api: NaruApiClient): Promise<string> {
  const reg = await navigator.serviceWorker.ready;
  const existing = await reg.pushManager.getSubscription();
  const sub =
    existing ??
    (await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: keyBytes((await api.vapidPublicKey()).public_key).buffer as ArrayBuffer,
    }));
  const json = sub.toJSON();
  if (!json.endpoint || !json.keys) throw new Error("구독에 endpoint·keys 가 없다");
  await api.pushSubscribe({
    endpoint: json.endpoint,
    expirationTime: json.expirationTime ?? null,
    keys: { p256dh: json.keys["p256dh"] ?? "", auth: json.keys["auth"] ?? "" },
  });
  writeEndpoint(json.endpoint);
  return json.endpoint;
}

/** 내 위치를 켰을 때만 — 구독이 있으면 마지막 위치(서버가 150 m 격자·3시간) */
export function lastSeenFrom(api: NaruApiClient, point: readonly [number, number]): void {
  const endpoint = readStore().endpoint ?? readEndpoint();
  if (!endpoint) return;
  api
    .addWatchArea({
      endpoint,
      kind: "last_seen",
      lng: point[0],
      lat: point[1],
      radius_m: WATCH_RADIUS_M,
    })
    .then(() => refreshAreas(api, endpoint))
    .catch(() => undefined);
}

export interface PushActions {
  enable: () => void;
  disable: () => void;
  /** 사건 중심 반경 500 m 를 저장 관심 지역으로 (구독이 없으면 먼저 켠다) */
  watch: (point: readonly [number, number], label: string) => void;
  unwatch: (id: number) => void;
  watchedArea: (point: readonly [number, number]) => WatchArea | null;
}

let booted = false;

export function usePush(): PushStore & PushActions {
  const api = useNaruApi();
  const store = useSyncExternalStore(subscribeStore, readStore, readStore);
  useEffect(() => {
    if (booted) return;
    booted = true;
    const env = readEnv();
    setStore({ support: pushSupport(env), labels: readLabels() });
    if (!env.serviceWorker) return;
    navigator.serviceWorker
      .register(SW_URL, { scope: "/" })
      .catch(() => setStore({ support: "unsupported" }));
    const endpoint = readEndpoint();
    if (endpoint && env.permission === "granted") void refreshAreas(api, endpoint);
  }, [api]);

  const enable = useCallback(() => {
    if (!("Notification" in window)) return;
    setStore({ busy: true, error: null });
    Notification.requestPermission()
      .then(async (permission) => {
        setStore({ support: pushSupport({ ...readEnv(), permission }) });
        if (permission !== "granted") return;
        const endpoint = await ensureSubscribed(api);
        await refreshAreas(api, endpoint);
      })
      .catch(() => setStore({ error: "failed" }))
      .finally(() => setStore({ busy: false }));
  }, [api]);

  const disable = useCallback(() => {
    const endpoint = readStore().endpoint;
    if (!endpoint) return;
    setStore({ busy: true });
    api
      .pushUnsubscribe(endpoint)
      .then(async () => {
        const reg = await navigator.serviceWorker.ready;
        await (await reg.pushManager.getSubscription())?.unsubscribe();
      })
      .catch(() => undefined)
      .finally(() => {
        writeEndpoint(null);
        setStore({ endpoint: null, areas: [], busy: false });
      });
  }, [api]);

  const watch = useCallback(
    (point: readonly [number, number], label: string) => {
      setStore({ busy: true, error: null });
      (async () => {
        const endpoint = readStore().endpoint ?? (await ensureSubscribed(api));
        const area = await api.addWatchArea({
          endpoint,
          kind: "saved",
          lng: point[0],
          lat: point[1],
          radius_m: WATCH_RADIUS_M,
        });
        const labels = { ...readLabels(), [String(area.id)]: label };
        writeLabels(labels);
        setStore({ labels });
        await refreshAreas(api, endpoint);
      })()
        .catch((e: unknown) => {
          const limit = e instanceof NaruApiError && e.status === 400;
          setStore({ error: limit ? "limit" : "failed" });
        })
        .finally(() => setStore({ busy: false }));
    },
    [api],
  );

  const unwatch = useCallback(
    (id: number) => {
      const endpoint = readStore().endpoint;
      if (!endpoint) return;
      api
        .removeWatchArea(id, endpoint)
        .then(() => refreshAreas(api, endpoint))
        .catch(() => undefined);
    },
    [api],
  );

  const watched = useCallback(
    (point: readonly [number, number]) => watchedArea(store.areas, point),
    [store.areas],
  );
  return { ...store, enable, disable, watch, unwatch, watchedArea: watched };
}
