import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Footer } from "../components/Footer";
import { Providers } from "./providers";
import "./globals.css";

// Server Component — HTML 뼈대·메타데이터·푸터만 (CONVENTIONS §5.3)
export const metadata: Metadata = {
  title: "나루 — 통제 우회 보행 안내",
  description: "마라톤·집회로 횡단보도가 막힐 때 지하도·육교로 건너는 길",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <Providers>{children}</Providers>
        <Footer />
      </body>
    </html>
  );
}
