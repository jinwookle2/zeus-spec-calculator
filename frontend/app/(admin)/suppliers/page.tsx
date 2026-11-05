"use client";

import { useState } from "react";
import { Badge, Btn, Msg, Page, Table, useApi } from "@/components/ui";
import { api } from "@/lib/api";

const FLAGS: [string, string][] = [
  ["verified", "검증됨"], ["auto_listing_allowed", "자동 등록"], ["auto_purchase_allowed", "자동 발주"],
  ["image_usage_allowed", "이미지 사용권"], ["pii_transfer_agreed", "개인정보 전달 계약"], ["active", "활성"],
];

export default function Suppliers() {
  const { data, reload } = useApi<any[]>("/suppliers");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [form, setForm] = useState({ code: "", name: "", adapter_type: "mock", path: "" });

  async function act(fn: () => Promise<unknown>, ok: string) {
    try { await fn(); setMsg(ok); setErr(null); } catch (e) { setErr((e as Error).message); setMsg(null); }
    reload();
  }
  const toggle = (s: any, k: string) => act(() => api(`/suppliers/${s.id}`, { method: "PATCH", body: { [k]: !s[k] } }), `${s.code} ${k} 변경`);
  const sync = (s: any) => act(async () => { const r = await api(`/suppliers/${s.id}/sync`, { method: "POST" }); setMsg(JSON.stringify(r)); }, `${s.code} 수집 완료`);
  const create = () => act(() => api("/suppliers", { method: "POST", body: {
    code: form.code, name: form.name, adapter_type: form.adapter_type,
    config: form.adapter_type === "csv" ? { path: form.path } : { prefix: form.code.slice(0, 2) },
  } }), "공급사 추가됨");

  return (
    <Page title="공급사 관리" desc="공급사별 검증 상태와 자동화 허용 범위를 관리합니다. 검증된 공급사만 자동 등록/발주가 허용됩니다.">
      <Msg text={msg} /><Msg text={err} tone="error" />
      <Table testId="suppliers-table" rows={data} cols={[
        { key: "code", label: "코드" }, { key: "name", label: "이름" }, { key: "adapter_type", label: "연동" },
        { key: "product_count", label: "상품" },
        ...FLAGS.map(([k, label]) => ({ key: k, label, render: (s: any) => (
          <button onClick={() => toggle(s, k)} className={`rounded px-2 py-0.5 text-xs ${s[k] ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-500"}`}>{s[k] ? "ON" : "OFF"}</button>
        ) })),
        { key: "auto_purchase_paused", label: "자동발주 중단", render: (s: any) => s.auto_purchase_paused ? (
          <div className="space-y-1"><Badge value="ON_HOLD" /><div className="max-w-xs text-xs text-red-700">{s.pause_reason}</div>
            <Btn tone="ghost" onClick={() => act(() => api(`/suppliers/${s.id}`, { method: "PATCH", body: { auto_purchase_paused: false } }), "자동 발주 재개")}>재개</Btn></div>
        ) : <span className="text-slate-400">-</span> },
        { key: "brands", label: "판매권한 브랜드", render: (s: any) => (s.authorized_brands || []).join(", ") || "-" },
        { key: "a", label: "", render: (s: any) => <Btn testId={`sync-${s.code}`} onClick={() => sync(s)}>상품 수집</Btn> },
      ]} />
      <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
        <h2 className="mb-2 font-semibold">공급사 추가 (admin)</h2>
        <div className="flex flex-wrap gap-2">
          <input placeholder="코드 (영문)" className="rounded border px-2 py-1" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} />
          <input placeholder="이름" className="rounded border px-2 py-1" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <select className="rounded border px-2 py-1" value={form.adapter_type} onChange={(e) => setForm({ ...form, adapter_type: e.target.value })}>
            <option value="mock">Mock</option><option value="csv">CSV/Excel 피드</option>
          </select>
          {form.adapter_type === "csv" && <input placeholder="서버 내 파일 경로" className="rounded border px-2 py-1" value={form.path} onChange={(e) => setForm({ ...form, path: e.target.value })} />}
          <Btn onClick={create}>추가</Btn>
        </div>
        <p className="mt-2 text-xs text-slate-500">실제 공급사 API는 계약/명세 확보 후 backend/app/adapters 에 Adapter를 추가합니다. 인증 비밀값은 환경변수로만 주입합니다.</p>
      </div>
    </Page>
  );
}
