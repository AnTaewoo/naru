// 네트워크를 만지는 유일한 파일 (CONVENTIONS §5.4). 같은 오리진 /api/* → Next rewrites → Flask.
import type {
  ClosureEventsResponse,
  ErrorBody,
  FeatureCollection,
  GeocodeReverseResponse,
  GeocodeSearchResponse,
  Place,
  RouteResponse,
} from "../types/contracts";

export interface RouteParams {
  /** "lat,lng" (INTERFACE §2) */
  from: string;
  to: string;
  /** ISO 8601 + 오프셋 */
  departAt: string;
}

export interface ClosuresParams {
  /** "minLng,minLat,maxLng,maxLat" (INTERFACE §3) */
  bbox: string;
  at: string;
}

export interface EventsParams {
  /** "minLng,minLat,maxLng,maxLat" — 없으면 전체 (INTERFACE §3.1) */
  bbox?: string;
}

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
  return `${baseUrl}/route?${q.toString()}`;
}

export function closuresUrl(baseUrl: string, p: ClosuresParams): string {
  const q = new URLSearchParams({ bbox: p.bbox, at: p.at });
  return `${baseUrl}/closures?${q.toString()}`;
}

export function eventsUrl(baseUrl: string, p: EventsParams = {}): string {
  const q = new URLSearchParams();
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
  return json as unknown as ClosureEventsResponse;
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

export function parseGeocodeReverse(json: unknown): GeocodeReverseResponse {
  const label: unknown = isRecord(json) ? json.label : undefined;
  if (label !== null && typeof label !== "string") throw new NaruApiError(200, null);
  return json as unknown as GeocodeReverseResponse;
}

export interface NaruApiClient {
  readonly baseUrl: string;
  route(p: RouteParams, signal?: AbortSignal): Promise<RouteResponse>;
  closures(p: ClosuresParams, signal?: AbortSignal): Promise<FeatureCollection>;
  events(p?: EventsParams, signal?: AbortSignal): Promise<ClosureEventsResponse>;
  geocodeSearch(p: GeocodeSearchParams, signal?: AbortSignal): Promise<GeocodeSearchResponse>;
  geocodeReverse(p: GeocodeReverseParams, signal?: AbortSignal): Promise<GeocodeReverseResponse>;
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
    events: async (p, signal) =>
      parseClosureEvents(await getJson(eventsUrl(baseUrl, p), fetchImpl, signal)),
    geocodeSearch: async (p, signal) =>
      parseGeocodeSearch(await getJson(geocodeSearchUrl(baseUrl, p), fetchImpl, signal)),
    geocodeReverse: async (p, signal) =>
      parseGeocodeReverse(await getJson(geocodeReverseUrl(baseUrl, p), fetchImpl, signal)),
  };
}
