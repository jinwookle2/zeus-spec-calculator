"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const MENU = [
  ["/", "대시보드"], ["/suppliers", "공급사 관리"], ["/sourcing", "상품 소싱"], ["/listing-queue", "상품 등록 대기"],
  ["/products", "등록 상품 관리"], ["/pricing", "가격 및 마진 관리"], ["/inventory", "재고 관리"], ["/orders", "주문 관리"],
  ["/purchases", "공급사 발주"], ["/shipping", "배송 관리"], ["/analytics", "매출 및 수익 분석"], ["/alerts", "오류 및 알림"],
  ["/automation", "자동화 설정"], ["/connections", "API 연결 설정"],
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [me, setMe] = useState<{ email: string; role: string } | null>(null);
  const [health, setHealth] = useState<{ naver_mode: string; safety: Record<string, boolean> } | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!localStorage.getItem("token")) {
      window.location.href = "/login";
      return;
    }
    api("/auth/me").then(setMe).catch(() => {});
    fetch("/health").then((r) => r.json()).then(setHealth).catch(() => {});
  }, []);
  const live = health?.naver_mode === "live";
  const anyGateOpen = health && Object.values(health.safety).some(Boolean);
  return (
    <div className="min-h-screen md:flex">
      <aside className={`${open ? "block" : "hidden"} w-full shrink-0 bg-slate-900 text-slate-200 md:block md:w-56`}>
        <div className="px-4 py-4 text-sm font-bold text-white">SmartStore 자동화</div>
        <nav className="space-y-0.5 px-2 pb-4">
          {MENU.map(([href, label]) => (
            <Link key={href} href={href} onClick={() => setOpen(false)}
              className={`block rounded px-3 py-2 text-sm ${path === href ? "bg-slate-700 text-white" : "hover:bg-slate-800"}`}>
              {label}
            </Link>
          ))}
        </nav>
      </aside>
      <div className="min-w-0 flex-1">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-2 text-xs">
          <button className="rounded border px-2 py-1 md:hidden" onClick={() => setOpen(!open)}>메뉴</button>
          <div className="flex flex-wrap gap-2">
            <span data-testid="mode-badge" className={`rounded px-2 py-0.5 font-semibold ${live ? "bg-red-100 text-red-700" : "bg-emerald-100 text-emerald-700"}`}>
              네이버 {live ? "LIVE" : "MOCK"}
            </span>
            <span className={`rounded px-2 py-0.5 ${anyGateOpen ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-600"}`}>
              {anyGateOpen ? "⚠ 실제 실행 스위치 일부 활성" : "안전 스위치 모두 OFF (Dry-run)"}
            </span>
          </div>
          <div className="flex items-center gap-3 text-slate-600">
            <span>{me?.email} ({me?.role})</span>
            <button className="underline" onClick={() => { localStorage.clear(); window.location.href = "/login"; }}>로그아웃</button>
          </div>
        </header>
        <main className="p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
