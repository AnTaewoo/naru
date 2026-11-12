"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";
import { createNaruApiClient, type NaruApiClient } from "../api/naruApiClient";

// Provider 1/4 — BE 클라이언트 하나를 트리에 준다. 상태가 없으니 state/dispatch 분리 대상이 아니다
const ApiCtx = createContext<NaruApiClient | null>(null);

export function ApiProvider({ children, client }: { children: ReactNode; client?: NaruApiClient }) {
  const value = useMemo(() => client ?? createNaruApiClient(), [client]);
  return <ApiCtx.Provider value={value}>{children}</ApiCtx.Provider>;
}

export function useNaruApi(): NaruApiClient {
  const v = useContext(ApiCtx);
  if (!v) throw new Error("ApiProvider 밖에서 useNaruApi 호출");
  return v;
}
