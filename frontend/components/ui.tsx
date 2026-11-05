"use client";

import { ReactNode, useCallback, useEffect, useState } from "react";
import { api, Json } from "@/lib/api";

export function useApi<T = Json>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const reload = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    try {
      setData(await api<T>(path));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    reload();
  }, [reload]);
  return { data, error, loading, reload };
}

export function Page({ title, desc, actions, children }: { title: string; desc?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900">{title}</h1>
          {desc && <p className="text-sm text-slate-500">{desc}</p>}
        </div>
        <div className="flex flex-wrap gap-2">{actions}</div>
      </div>
      {children}
    </div>
  );
}

export function Card({ title, children, className = "" }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-slate-200 bg-white p-4 shadow-sm ${className}`}>
      {title && <h2 className="mb-3 text-sm font-semibold text-slate-700">{title}</h2>}
      {children}
    </div>
  );
}

export function Stat({ label, value, tone = "slate" }: { label: string; value: ReactNode; tone?: string }) {
  const tones: Record<string, string> = { slate: "text-slate-900", red: "text-red-600", amber: "text-amber-600", green: "text-emerald-600" };
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${tones[tone]}`}>{value}</div>
    </div>
  );
}

const BADGE: Record<string, string> = {
  LISTED: "bg-emerald-100 text-emerald-800", APPROVED: "bg-sky-100 text-sky-800", PENDING_APPROVAL: "bg-amber-100 text-amber-800",
  BLOCKED: "bg-red-100 text-red-800", FAILED: "bg-red-100 text-red-800", SUSPENDED: "bg-slate-200 text-slate-700",
  SOLD_OUT: "bg-slate-200 text-slate-700", ACTIVE: "bg-emerald-100 text-emerald-800", DUPLICATE: "bg-purple-100 text-purple-800",
  DISCONTINUED: "bg-slate-200 text-slate-700", PAID: "bg-sky-100 text-sky-800", STOCK_CHECKED: "bg-sky-100 text-sky-800",
  PURCHASE_REQUESTED: "bg-indigo-100 text-indigo-800", SUPPLIER_CONFIRMED: "bg-indigo-100 text-indigo-800",
  SHIPPED: "bg-teal-100 text-teal-800", TRACKING_REGISTERED: "bg-teal-100 text-teal-800", DELIVERED: "bg-emerald-100 text-emerald-800",
  AWAITING_APPROVAL: "bg-amber-100 text-amber-800", ON_HOLD: "bg-orange-100 text-orange-800", CANCELLED: "bg-slate-200 text-slate-700",
  CANCEL_REQUESTED: "bg-orange-100 text-orange-800", RETURN_REQUESTED: "bg-orange-100 text-orange-800",
  CONFIRMED: "bg-indigo-100 text-indigo-800", REQUESTING: "bg-amber-100 text-amber-800", REQUESTED: "bg-indigo-100 text-indigo-800",
  error: "bg-red-100 text-red-800", critical: "bg-red-200 text-red-900", warning: "bg-amber-100 text-amber-800", info: "bg-slate-100 text-slate-700",
};

export function Badge({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="text-slate-400">-</span>;
  return <span className={`inline-block whitespace-nowrap rounded px-2 py-0.5 text-xs font-medium ${BADGE[value] || "bg-slate-100 text-slate-700"}`}>{value}</span>;
}

export type Col<T> = { key: string; label: string; render?: (row: T) => ReactNode; className?: string };

export function Table<T extends Json>({ rows, cols, empty = "데이터가 없습니다", testId }: { rows: T[] | null; cols: Col<T>[]; empty?: string; testId?: string }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full text-sm" data-testid={testId}>
        <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
          <tr>{cols.map((c) => <th key={c.key} className="whitespace-nowrap px-3 py-2 font-medium">{c.label}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows === null ? (
            <tr><td className="px-3 py-6 text-center text-slate-400" colSpan={cols.length}>불러오는 중…</td></tr>
          ) : rows.length === 0 ? (
            <tr><td className="px-3 py-6 text-center text-slate-400" colSpan={cols.length}>{empty}</td></tr>
          ) : (
            rows.map((r, i) => (
              <tr key={(r as Json).id ?? i} className="hover:bg-slate-50">
                {cols.map((c) => <td key={c.key} className={`px-3 py-2 align-top ${c.className || ""}`}>{c.render ? c.render(r) : String((r as Json)[c.key] ?? "-")}</td>)}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export function Btn({ children, onClick, tone = "primary", disabled, testId }: { children: ReactNode; onClick?: () => void; tone?: "primary" | "ghost" | "danger"; disabled?: boolean; testId?: string }) {
  const tones = {
    primary: "bg-slate-900 text-white hover:bg-slate-700",
    ghost: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
    danger: "bg-red-600 text-white hover:bg-red-500",
  };
  return (
    <button data-testid={testId} disabled={disabled} onClick={onClick} className={`whitespace-nowrap rounded px-3 py-1.5 text-xs font-medium disabled:opacity-40 ${tones[tone]}`}>
      {children}
    </button>
  );
}

export function Msg({ text, tone = "info" }: { text: string | null; tone?: "info" | "error" }) {
  if (!text) return null;
  return <div className={`rounded border px-3 py-2 text-sm ${tone === "error" ? "border-red-200 bg-red-50 text-red-700" : "border-emerald-200 bg-emerald-50 text-emerald-700"}`}>{text}</div>;
}

export function Reasons({ items }: { items: string[] | undefined }) {
  if (!items || items.length === 0) return <span className="text-slate-400">-</span>;
  return <ul className="space-y-0.5 text-xs text-red-700">{items.map((x) => <li key={x}>• {x}</li>)}</ul>;
}

export function Filter({ value, onChange, options }: { value: string; onChange: (v: string) => void; options: string[] }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)} className="rounded border border-slate-300 bg-white px-2 py-1 text-sm">
      <option value="">전체</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}
