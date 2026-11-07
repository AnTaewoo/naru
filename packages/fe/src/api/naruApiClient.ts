// 네트워크를 만지는 유일한 파일 (CONVENTIONS §5.4). 같은 오리진 /api/* → Next rewrites → Flask.
import type { ErrorBody, FeatureCollection, RouteResponse } from "../types/contracts";

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

export interface NaruApiClient {
  readonly baseUrl: string;
  route(p: RouteParams, signal?: AbortSignal): Promise<RouteResponse>;
  closures(p: ClosuresParams, signal?: AbortSignal): Promise<FeatureCollection>;
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
  };
}
