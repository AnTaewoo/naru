// 배경 타일 스타일 — VWorld(키 있을 때) / OSM(키 없을 때 개발용). 순수 함수
// 글리프(폰트) 없음 — 지도 표식은 icons.ts 가 캔버스로 그린다
import type { StyleSpecification } from "maplibre-gl";

export const VWORLD_TILE = (key: string) =>
  `https://api.vworld.kr/req/wmts/1.0.0/${key}/Base/{z}/{y}/{x}.png`;
export const OSM_TILE = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export function baseStyle(vworldKey: string | undefined): StyleSpecification {
  const useVworld = Boolean(vworldKey);
  return {
    version: 8,
    sources: {
      base: {
        type: "raster",
        tiles: [useVworld ? VWORLD_TILE(vworldKey ?? "") : OSM_TILE],
        tileSize: 256,
        attribution: useVworld
          ? "© VWorld (국토교통부)"
          : "© OpenStreetMap contributors (VWorld 키 없음 — 개발용)",
        maxzoom: 19,
      },
    },
    layers: [{ id: "base", type: "raster", source: "base" }],
  };
}
