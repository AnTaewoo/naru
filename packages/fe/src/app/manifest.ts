import type { MetadataRoute } from "next";

// PWA 매니페스트 (ADR-014 D, T7.7) — Next App Router 가 /manifest.webmanifest 로 낸다. 홈 화면 설치·알림(B)의 바탕.
// 아이콘은 app/icon.svg 를 PNG 로 뜬 것(public/icons, magick) — maskable 은 안전 영역 80% 에 아이콘
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "나루 — 통제 우회 보행 안내",
    short_name: "나루",
    description: "마라톤·집회로 횡단보도가 막힐 때 지하도·육교로 건너는 길",
    lang: "ko",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#2d6bff",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
      {
        src: "/icons/icon-512-maskable.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable",
      },
    ],
  };
}
