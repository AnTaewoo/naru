// 네트워크를 만지는 유일한 파일 (CONVENTIONS §5.4). 같은 오리진 /api/* → Next rewrites → Flask.
import type {
  ClosureEventsResponse,
  ErrorBody,
  FeatureCollection,
  GeocodeReverseResponse,
  GeocodeSearchResponse,
  MarchResponse,
  NearestCrosswalk,
  PushSubscription as PushSubscriptionBody,
  SubscribeResponse,
  VapidPublicKey,
  WatchArea,
  WatchAreaRequest,
  WatchAreasResponse,
  NearestCrosswalkQuery,
  NearestCrosswalkResponse,
  Place,
  RecentReportsResponse,
  ReportRequest,
  ReportResponse,
  RouteResponse,
} from "../types/contracts";

export interface RouteParams {
  /** "lat,lng" (INTERFACE §2) */
  from: string;
  to: string;
  /** ISO 8601 + 오프셋 */
  departAt: string;
  /** 피할 사건 id (INTERFACE §2 v0.14 avoid, T7.6) — 시각·확신도와 상관없이 막는다 */
  avoid?: readonly string[];
}

export interface ClosuresParams {
  /** "minLng,minLat,maxLng,maxLat" (INTERFACE §3) */
  bbox: string;
  at: string;
}

export interface EventsParams {
  /** "minLng,minLat,maxLng,maxLat" — 없으면 전체 (INTERFACE §3.1) */
  bbox?: string;
  /** ISO 8601 + 오프셋 — 사건 status 의 기준 시각, 기본 창 = 그때 진행 중 + 다음 날 24:00 KST (v0.14) */
  at?: string;
  /** at 과 같이 — 창을 넓힌다(시트 목록 T7.12: at 앞뒤 365일) */
  from?: string;
  to?: string;
}

/** 사건 조건부 요청 결과 (T7.4) — 304 면 바뀐 것 없음(본문 없음) */
export type EventsFetch =
  | { changed: false; etag: string }
  | { changed: true; etag: string | null; body: ClosureEventsResponse };

export interface GeocodeSearchParams {
  /** 검색어 2~50자 (INTERFACE §7.1) */
  q: string;
  /** "lat,lng" — 있으면 반경 5 km 안 정확도 순 */
  near?: string;
}

export interface GeocodeReverseParams {
  lat: number;
  lng: number;
}

/** 행진 키프레임 (INTERFACE §3.2, T7.16) — from·to 없으면 통제 시간 전체 */
export interface MarchParams {
  from?: string;
  to?: string;
}

/** 최근 제보 수 (INTERFACE §8.3, T7.15) */
export interface RecentReportsParams {
  /** 횡단보도 ID 1~50개 */
  ids: readonly string[];
  /** 기본 60 */
  minutes?: number;
}

/** 구독 endpoint 를 헤더로 (INTERFACE §9 — 주소·접근 로그에 안 남게) */
export const PUSH_ENDPOINT_HEADER = "X-Push-Endpoint";

export class NaruApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ErrorBody | null,
  ) {
    super(body ? `${body.error.code}: ${body.error.message}` : `HTTP ${status}`);
    this.name = "NaruApiError";
  }
}

export function routeUrl(baseUrl: string, p: RouteParams): string {
  const q = new URLSearchParams({ from: p.from, to: p.to, depart_at: p.departAt, mode: "walk" });
  if (p.avoid && p.avoid.length > 0) q.set("avoid", p.avoid.join(","));
  return `${baseUrl}/route?${q.toString()}`;
}

export function closuresUrl(baseUrl: string, p: ClosuresParams): string {
  const q = new URLSearchParams({ bbox: p.bbox, at: p.at });
  return `${baseUrl}/closures?${q.toString()}`;
}

export function eventsUrl(baseUrl: string, p: EventsParams = {}): string {
  const q = new URLSearchParams();
  if (p.at) q.set("at", p.at);
  if (p.from) q.set("from", p.from);
  if (p.to) q.set("to", p.to);
  if (p.bbox) q.set("bbox", p.bbox);
  const qs = q.toString();
  return `${baseUrl}/closures/events${qs ? `?${qs}` : ""}`;
}

export function geocodeSearchUrl(baseUrl: string, p: GeocodeSearchParams): string {
  const q = new URLSearchParams({ q: p.q });
  if (p.near) q.set("near", p.near);
  return `${baseUrl}/geocode/search?${q.toString()}`;
}

export function geocodeReverseUrl(baseUrl: string, p: GeocodeReverseParams): string {
  const q = new URLSearchParams({ lat: String(p.lat), lng: String(p.lng) });
  return `${baseUrl}/geocode/reverse?${q.toString()}`;
}

/** 행진 키프레임 주소 (INTERFACE §3.2, T7.16) — 사건 id 는 §3.1 의 12자 소문자 16진수 */
export function marchUrl(baseUrl: string, eventId: string, p: MarchParams = {}): string {
  const q = new URLSearchParams();
  if (p.from) q.set("from", p.from);
  if (p.to) q.set("to", p.to);
  const qs = q.toString();
  return `${baseUrl}/closures/events/${eventId}/march${qs ? `?${qs}` : ""}`;
}

// 통제 제보 (INTERFACE §8, T7.15) — 좌표·제보는 주소가 아니라 POST 본문으로 (접근 로그에 안 남게)
export function nearestUrl(baseUrl: string): string {
  return `${baseUrl}/crosswalks/nearest`;
}

export function reportsUrl(baseUrl: string): string {
  return `${baseUrl}/reports`;
}

export function recentReportsUrl(baseUrl: string, p: RecentReportsParams): string {
  const q = new URLSearchParams({ ids: p.ids.join(","), minutes: String(p.minutes ?? 60) });
  return `${baseUrl}/reports/recent?${q.toString()}`;
}

export function postInit(
  body: unknown,
  signal?: AbortSignal,
): RequestInit & { headers: Record<string, string> } {
  return {
    method: "POST",
    signal,
    cache: "no-store",
    headers: { accept: "application/json", "content-type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function pushUrl(baseUrl: string, path: "vapid-public-key" | "subscribe"): string {
  return `${baseUrl}/push/${path}`;
}

export function watchAreasUrl(baseUrl: string, id?: number): string {
  return id === undefined ? `${baseUrl}/watch-areas` : `${baseUrl}/watch-areas/${id}`;
}

/** GET·DELETE 에 구독 endpoint 헤더 (본문이 있으면 JSON 으로) */
export function endpointInit(
  method: "GET" | "DELETE",
  endpoint: string,
  body?: unknown,
  signal?: AbortSignal,
): RequestInit & { headers: Record<string, string> } {
  return {
    method,
    signal,
    cache: "no-store",
    headers: {
      accept: "application/json",
      [PUSH_ENDPOINT_HEADER]: endpoint,
      ...(body === undefined ? {} : { "content-type": "application/json" }),
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  };
}

/** 2xx 가 아니면 §6 본문으로 NaruApiError (429 too_many_reports 도) */
export function readJson(status: number, json: unknown): unknown {
  if (status < 200 || status >= 300) {
    const body = isRecord(json) && isRecord(json.error) ? (json as unknown as ErrorBody) : null;
    throw new NaruApiError(status, body);
  }
  return json;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null;
}

/** 응답 모양 최소 검사 — 계약(contracts.d.ts)과 어긋난 응답은 여기서 터진다 */
export function parseRouteResponse(json: unknown): RouteResponse {
  if (
    !isRecord(json) ||
    !isRecord(json.route) ||
    !Array.isArray(json.legs) ||
    !Array.isArray(json.avoided) ||
    !isRecord(json.baseline) ||
    typeof json.computed_at !== "string"
  ) {
    throw new NaruApiError(200, null);
  }
  return json as unknown as RouteResponse;
}

export function parseFeatureCollection(json: unknown): FeatureCollection {
  if (!isRecord(json) || json.type !== "FeatureCollection" || !Array.isArray(json.features)) {
    throw new NaruApiError(200, null);
  }
  return json as unknown as FeatureCollection;
}

export function parseClosureEvents(json: unknown): ClosureEventsResponse {
  if (!isRecord(json) || !Array.isArray(json.events)) throw new NaruApiError(200, null);
  const coverage: unknown = json.coverage; // v0.10 부터 필수 — 보행망 bbox (T5.7)
  if (!Array.isArray(coverage) || coverage.length !== 4) throw new NaruApiError(200, null);
  if (!isRecord(json.data_as_of)) throw new NaruApiError(200, null); // v0.12 필수 (T5.9)
  if (typeof json.at !== "string") throw new NaruApiError(200, null); // v0.14 필수 (T7.1)
  return json as unknown as ClosureEventsResponse;
}

/**
 * 사건 요청 (T7.4) — 브라우저 HTTP 캐시를 거치지 않고(no-store) If-None-Match 를 직접 단다. 캐시에 맡기면
 * 304 가 캐시 본문 200 으로 바뀌어 JS 가 '그대로'를 모른다
 */
export function eventsInit(etag: string | null, signal?: AbortSignal): RequestInit {
  const headers: Record<string, string> = { accept: "application/json" };
  if (etag) headers["if-none-match"] = etag;
  return { signal, cache: "no-store", headers };
}

/** 사건 응답 읽기 — 304 는 바뀐 것 없음(ETag 머리가 없으면 보낸 것), 그 밖의 오류는 §6 본문 */
export function readEvents(
  status: number,
  etag: string | null,
  json: unknown,
  sent: string | null = null,
): EventsFetch {
  if (status === 304) {
    const tag = etag ?? sent;
    if (!tag) throw new NaruApiError(304, null);
    return { changed: false, etag: tag };
  }
  if (status < 200 || status >= 300) {
    const body = isRecord(json) && isRecord(json.error) ? (json as unknown as ErrorBody) : null;
    throw new NaruApiError(status, body);
  }
  return { changed: true, etag, body: parseClosureEvents(json) };
}

/** 장소 좌표 [lng, lat] (생성 타입이 unknown 튜플이라 숫자를 확인한다) */
export function placeLngLat(p: Place): [number, number] | null {
  const [lng, lat] = p.coord;
  return typeof lng === "number" && typeof lat === "number" ? [lng, lat] : null;
}

export function parseGeocodeSearch(json: unknown): GeocodeSearchResponse {
  const places: unknown = isRecord(json) ? json.places : null;
  const ok =
    Array.isArray(places) &&
    places.every(
      (p) =>
        isRecord(p) &&
        typeof p.name === "string" &&
        typeof p.address === "string" &&
        placeLngLat(p as unknown as Place) !== null,
    );
  if (!ok) throw new NaruApiError(200, null);
  return json as unknown as GeocodeSearchResponse;
}

/** 최근접 횡단보도 좌표 [lng, lat] (생성 타입이 unknown 튜플이라 숫자를 확인한다) */
export function crosswalkLngLat(c: NearestCrosswalk): [number, number] | null {
  const [lng, lat] = c.coord;
  return typeof lng === "number" && typeof lat === "number" ? [lng, lat] : null;
}

export function parseNearestCrosswalk(json: unknown): NearestCrosswalkResponse {
  if (!isRecord(json) || !("crosswalk" in json)) throw new NaruApiError(200, null);
  const c: unknown = json.crosswalk;
  const ok =
    c === null ||
    (isRecord(c) &&
      typeof c.id === "string" &&
      typeof c.name === "string" &&
      typeof c.district === "string" &&
      typeof c.distance_m === "number" &&
      Array.isArray(c.coord) &&
      crosswalkLngLat(c as unknown as NearestCrosswalk) !== null);
  if (!ok) throw new NaruApiError(200, null);
  return json as unknown as NearestCrosswalkResponse;
}

export function parseReportResponse(json: unknown): ReportResponse {
  const ok =
    isRecord(json) &&
    typeof json.id === "number" &&
    typeof json.crosswalk_id === "string" &&
    typeof json.reported_at === "string" &&
    (json.state === "blocked" || json.state === "open");
  if (!ok) throw new NaruApiError(200, null);
  return json as unknown as ReportResponse;
}

export function parseRecentReports(json: unknown): RecentReportsResponse {
  const counts: unknown = isRecord(json) ? json.counts : null;
  const ok =
    isRecord(counts) &&
    !Array.isArray(counts) &&
    Object.values(counts).every(
      (c) => isRecord(c) && typeof c.blocked === "number" && typeof c.open === "number",
    );
  if (!ok) throw new NaruApiError(200, null);
  return json as unknown as RecentReportsResponse;
}

export function parseMarch(json: unknown): MarchResponse {
  const ok =
    isRecord(json) &&
    typeof json.event_id === "string" &&
    typeof json.step_s === "number" &&
    isRecord(json.window) &&
    isRecord(json.crosswalk_points) &&
    Array.isArray(json.keyframes) &&
    json.keyframes.every(
      (k) =>
        isRecord(k) &&
        typeof k.t === "string" &&
        Array.isArray(k.samples) &&
        Array.isArray(k.center) &&
        typeof k.radius_m === "number" &&
        isRecord(k.crosswalks),
    );
  if (!ok) throw new NaruApiError(200, null);
  return json as unknown as MarchResponse;
}

/** 404 not_modeled(대상이 아닌 사건) 은 오류가 아니라 '모델 없음' */
export function marchOrNull(e: unknown): null {
  if (e instanceof NaruApiError && e.body?.error.code === "not_modeled") return null;
  throw e;
}

export function parseVapidPublicKey(json: unknown): VapidPublicKey {
  const ok = isRecord(json) && typeof json.public_key === "string" && json.public_key.length >= 87;
  if (!ok) throw new NaruApiError(200, null);
  return json as unknown as VapidPublicKey;
}

export function parseSubscribeResponse(json: unknown): SubscribeResponse {
  const ok =
    isRecord(json) &&
    typeof json.id === "number" &&
    typeof json.active === "boolean" &&
    typeof json.created_at === "string";
  if (!ok) throw new NaruApiError(200, null);
  return json as unknown as SubscribeResponse;
}

function isWatchArea(a: unknown): boolean {
  return (
    isRecord(a) &&
    typeof a.id === "number" &&
    (a.kind === "saved" || a.kind === "last_seen") &&
    typeof a.lng === "number" &&
    typeof a.lat === "number" &&
    typeof a.radius_m === "number"
  );
}

export function parseWatchArea(json: unknown): WatchArea {
  if (!isWatchArea(json)) throw new NaruApiError(200, null);
  return json as unknown as WatchArea;
}

export function parseWatchAreas(json: unknown): WatchAreasResponse {
  const areas: unknown = isRecord(json) ? json.areas : null;
  if (!Array.isArray(areas) || !areas.every(isWatchArea)) throw new NaruApiError(200, null);
  return json as unknown as WatchAreasResponse;
}

export function parseGeocodeReverse(json: unknown): GeocodeReverseResponse {
  const label: unknown = isRecord(json) ? json.label : undefined;
  if (label !== null && typeof label !== "string") throw new NaruApiError(200, null);
  return json as unknown as GeocodeReverseResponse;
}

export interface NaruApiClient {
  readonly baseUrl: string;
  route(p: RouteParams, signal?: AbortSignal): Promise<RouteResponse>;
  closures(p: ClosuresParams, signal?: AbortSignal): Promise<FeatureCollection>;
  /** etag 를 주면 조건부 — 그대로면 { changed: false } (T7.4) */
  events(p?: EventsParams, signal?: AbortSignal, etag?: string | null): Promise<EventsFetch>;
  geocodeSearch(p: GeocodeSearchParams, signal?: AbortSignal): Promise<GeocodeSearchResponse>;
  geocodeReverse(p: GeocodeReverseParams, signal?: AbortSignal): Promise<GeocodeReverseResponse>;
  /** 행진 예상 위치 키프레임 (T7.16) — 대상이 아닌 사건(404 not_modeled)은 null */
  march(eventId: string, p?: MarchParams, signal?: AbortSignal): Promise<MarchResponse | null>;
  /** 알림 구독·관심 지역 (INTERFACE §9, T7.10). endpoint 는 구독의 손잡이 */
  vapidPublicKey(signal?: AbortSignal): Promise<VapidPublicKey>;
  pushSubscribe(sub: PushSubscriptionBody, signal?: AbortSignal): Promise<SubscribeResponse>;
  pushUnsubscribe(endpoint: string, signal?: AbortSignal): Promise<void>;
  watchAreas(endpoint: string, signal?: AbortSignal): Promise<WatchAreasResponse>;
  addWatchArea(body: WatchAreaRequest, signal?: AbortSignal): Promise<WatchArea>;
  removeWatchArea(id: number, endpoint: string, signal?: AbortSignal): Promise<void>;
  /** 통제 제보 (T7.15) — 좌표는 본문으로 */
  nearestCrosswalk(
    p: NearestCrosswalkQuery,
    signal?: AbortSignal,
  ): Promise<NearestCrosswalkResponse>;
  report(body: ReportRequest, signal?: AbortSignal): Promise<ReportResponse>;
  recentReports(p: RecentReportsParams, signal?: AbortSignal): Promise<RecentReportsResponse>;
}

async function getJson(
  url: string,
  fetchImpl: typeof fetch,
  signal?: AbortSignal,
): Promise<unknown> {
  const res = await fetchImpl(url, { signal, headers: { accept: "application/json" } });
  const json: unknown = await res.json().catch(() => null);
  if (!res.ok) {
    const body = isRecord(json) && isRecord(json.error) ? (json as unknown as ErrorBody) : null;
    throw new NaruApiError(res.status, body);
  }
  return json;
}

async function postJson(
  url: string,
  body: unknown,
  fetchImpl: typeof fetch,
  signal?: AbortSignal,
): Promise<unknown> {
  const res = await fetchImpl(url, postInit(body, signal));
  const json: unknown = await res.json().catch(() => null);
  return readJson(res.status, json);
}

export function createNaruApiClient(
  baseUrl = "/api",
  fetchImpl: typeof fetch = (...args) => fetch(...args),
): NaruApiClient {
  return {
    baseUrl,
    route: async (p, signal) =>
      parseRouteResponse(await getJson(routeUrl(baseUrl, p), fetchImpl, signal)),
    closures: async (p, signal) =>
      parseFeatureCollection(await getJson(closuresUrl(baseUrl, p), fetchImpl, signal)),
    events: async (p, signal, etag = null) => {
      const res = await fetchImpl(eventsUrl(baseUrl, p), eventsInit(etag, signal));
      const json: unknown = res.status === 304 ? null : await res.json().catch(() => null);
      return readEvents(res.status, res.headers.get("etag"), json, etag);
    },
    geocodeSearch: async (p, signal) =>
      parseGeocodeSearch(await getJson(geocodeSearchUrl(baseUrl, p), fetchImpl, signal)),
    geocodeReverse: async (p, signal) =>
      parseGeocodeReverse(await getJson(geocodeReverseUrl(baseUrl, p), fetchImpl, signal)),
    march: async (eventId, p = {}, signal) =>
      getJson(marchUrl(baseUrl, eventId, p), fetchImpl, signal).then(parseMarch, marchOrNull),
    vapidPublicKey: async (signal) =>
      parseVapidPublicKey(await getJson(pushUrl(baseUrl, "vapid-public-key"), fetchImpl, signal)),
    pushSubscribe: async (sub, signal) =>
      parseSubscribeResponse(await postJson(pushUrl(baseUrl, "subscribe"), sub, fetchImpl, signal)),
    pushUnsubscribe: async (endpoint, signal) => {
      const init = endpointInit("DELETE", endpoint, { endpoint }, signal);
      const res = await fetchImpl(pushUrl(baseUrl, "subscribe"), init);
      if (!res.ok) readJson(res.status, await res.json().catch(() => null));
    },
    watchAreas: async (endpoint, signal) => {
      const init = endpointInit("GET", endpoint, undefined, signal);
      const res = await fetchImpl(watchAreasUrl(baseUrl), init);
      return parseWatchAreas(readJson(res.status, await res.json().catch(() => null)));
    },
    addWatchArea: async (body, signal) =>
      parseWatchArea(await postJson(watchAreasUrl(baseUrl), body, fetchImpl, signal)),
    removeWatchArea: async (id, endpoint, signal) => {
      const init = endpointInit("DELETE", endpoint, undefined, signal);
      const res = await fetchImpl(watchAreasUrl(baseUrl, id), init);
      if (!res.ok) readJson(res.status, await res.json().catch(() => null));
    },
    nearestCrosswalk: async (p, signal) =>
      parseNearestCrosswalk(await postJson(nearestUrl(baseUrl), p, fetchImpl, signal)),
    report: async (body, signal) =>
      parseReportResponse(await postJson(reportsUrl(baseUrl), body, fetchImpl, signal)),
    recentReports: async (p, signal) =>
      parseRecentReports(await getJson(recentReportsUrl(baseUrl, p), fetchImpl, signal)),
  };
}
