"use client";

import type { ReactNode } from "react";
import { ApiProvider } from "../state/ApiProvider";
import { ClosureProvider } from "../state/ClosureProvider";
import { RouteProvider } from "../state/RouteProvider";
import { TimeProvider } from "../state/TimeProvider";

// 'use client' 경계 1/2 — Provider 묶음. ApiProvider > TimeProvider > ClosureProvider > RouteProvider
export function Providers({ children }: { children: ReactNode }) {
  return (
    <ApiProvider>
      <TimeProvider>
        <ClosureProvider>
          <RouteProvider>{children}</RouteProvider>
        </ClosureProvider>
      </TimeProvider>
    </ApiProvider>
  );
}
