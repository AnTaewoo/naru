# packages/fe — Naru FE (Next.js App Router)

화면만 맡는다. 백엔드는 Flask 하나, 호출은 같은 오리진 `/api/*` → `next.config.ts` rewrites (CONVENTIONS §5).

```
pnpm install            # Node >= 18.18 (이 머신 18.20 → Next 15.5 고정, ADR-006)
pnpm dev                # :3000. BE 는 make dev-be (:5000) 또는 make dev 로 둘 다
pnpm check              # tsc + eslint + prettier + vitest — make check 가 부른다
pnpm e2e                # Playwright. make dev 가 떠 있어야 한다. 브라우저: NARU_CHROME_PATH=/usr/local/bin/google-chrome
```

- 시연 시각: `http://localhost:3000/?t=2026-03-15T07:45:00+09:00` (서울마라톤 통제 중). `?t=` 없으면 지금
- 시연 길찾기: `http://localhost:3000/?t=2026-03-15T07:45:00+09:00&from=37.5709686446227,126.9779039768265&to=37.5650416322942,126.976542945622` (교보빌딩 앞 → 대한문, recorded `/route` 와 같은 질의 — 지하보도로 건너는 우회). `t` 를 13:30 으로 바꾸면 원래 길. 홈의 길찾기 바를 누르고 지도를 두 번 눌러도 된다
- 지도 타일: `NEXT_PUBLIC_VWORLD_KEY` 가 있으면 VWorld, 없으면 OSM(개발용). VWorld 키는 서비스 URL(도메인)에 묶인다
- maplibre v6 워커는 `new URL(..., import.meta.url)` 로 webpack 이 `.next/static/media` 에 내보낸다(MapView.tsx)

- 타입 `src/types/contracts.d.ts` 는 `make schema` 생성물. 손으로 고치지 않는다
- 테스트 입력은 `data/recorded/naru_api/` (실제 Flask 응답). fetch 를 가로채지 않는다
- `'use client'` 는 `app/providers.tsx` 와 `components/NaruApp.tsx` 둘뿐. `@` 별칭 없이 상대 경로
- 환경변수: `NARU_API_ORIGIN`(서버 전용, 기본 http://127.0.0.1:5000 — localhost 는 Node 18 에서 ::1 이라 Flask 에 안 닿는다), `NEXT_PUBLIC_VWORLD_KEY`(T5.1)
