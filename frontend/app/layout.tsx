import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "스마트스토어 위탁판매 자동화", description: "운영 관리자" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
