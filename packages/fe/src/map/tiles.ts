// 배경 타일 스타일 — VWorld(키 있을 때) / OSM(키 없을 때 개발용). 순수 함수
// 글리프(폰트) 없음 — 지도 표식은 icons.ts 가 캔버스로 그린다
import type { StyleSpecification } from "maplibre-gl";

export const VWORLD_TILE = (key: string) =>
  `https://api.vworld.kr/req/wmts/1.0.0/${key}/Base/{z}/{y}/{x}.png`;
export const OSM_TILE = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
export const OSM_ATTRIBUTION =
  '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors</a>';

export function baseStyle(vworldKey: string | undefined): StyleSpecification {
  const useVworld = Boolean(vworldKey);
  return {
    version: 8,
    sources: {
      base: {
        type: "raster",
        tiles: [useVworld ? VWORLD_TILE(vworldKey ?? "") : OSM_TILE],
        tileSize: 256,
        // VWorld 키가 들어올 때까지 OSM (태우, 2026-11-08). 문구는 OSM 저작권 안내 그대로
        attribution: useVworld ? "© VWorld (국토교통부)" : OSM_ATTRIBUTION,
        maxzoom: 19,
      },
    },
    layers: [{ id: "base", type: "raster", source: "base" }],
  };
}
