"use client";

import type { ReactNode } from "react";
import { ApiProvider } from "../state/ApiProvider";

// 'use client' 경계 1/2 — Provider 묶음. ApiProvider > TimeProvider > ClosureProvider > RouteProvider
// (Time·Closure 는 T5.1, Route 는 T5.2 에서 이 안에 추가한다. CONVENTIONS §5.5)
export function Providers({ children }: { children: ReactNode }) {
  return <ApiProvider>{children}</ApiProvider>;
}
