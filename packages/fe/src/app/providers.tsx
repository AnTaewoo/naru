"use client";

import type { ReactNode } from "react";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider } from "../state/ClosureProvider";
import { TimeProvider } from "../state/TimeProvider";

// 'use client' 경계 1/2 — Provider 묶음. ApiProvider > TimeProvider > ClosureProvider > RouteProvider(T5.2)
export function Providers({ children }: { children: ReactNode }) {
  return (
    <ApiProvider>
      <TimeProvider>
        <ClosureProvider>{children}</ClosureProvider>
      </TimeProvider>
    </ApiProvider>
  );
}
