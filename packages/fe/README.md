# packages/fe — Naru FE (Next.js App Router)

화면만 맡는다. 백엔드는 Flask 하나, 호출은 같은 오리진 `/api/*` → `next.config.ts` rewrites (CONVENTIONS §5).

```
pnpm install            # Node >= 18.18 (이 머신 18.20 → Next 15.5 고정, ADR-006)
pnpm dev                # :3000. BE 는 make dev-be (:5000) 또는 make dev 로 둘 다
pnpm check              # tsc + eslint + prettier + vitest — make check 가 부른다
pnpm e2e                # Playwright. make dev 가 떠 있어야 한다
```

- 타입 `src/types/contracts.d.ts` 는 `make schema` 생성물. 손으로 고치지 않는다
- 테스트 입력은 `data/recorded/naru_api/` (실제 Flask 응답). fetch 를 가로채지 않는다
- `'use client'` 는 `app/providers.tsx` 와 `components/NaruApp.tsx` 둘뿐. `@` 별칭 없이 상대 경로
- 환경변수: `NARU_API_ORIGIN`(서버 전용, 기본 http://localhost:5000), `NEXT_PUBLIC_VWORLD_KEY`(T5.1)
