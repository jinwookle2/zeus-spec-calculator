"use client";

import { useState } from "react";
import { Badge, Btn, Msg, Page, Table, useApi } from "@/components/ui";
import { api } from "@/lib/api";

export default function Shipping() {
  const { data, reload } = useApi<any[]>("/shipments");
  const [form, setForm] = useState<Record<number, { carrier: string; no: string }>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function act(fn: () => Promise<any>, ok: string) {
    try { const r = await fn(); setMsg(`${ok} ${JSON.stringify(r).slice(0, 160)}`); setErr(null); } catch (e) { setErr((e as Error).message); }
    reload();
  }
  return (
    <Page title="배송 관리" desc="공급사 송장 수집 → 택배사 코드 매핑 → 네이버 발송처리. 발송처리 실패/매핑 실패는 오류 및 알림에 기록됩니다."
      actions={<Btn testId="poll-shipments" onClick={() => act(() => api("/jobs/poll_shipments/run", { method: "POST" }), "송장 수집:")}>송장 수집 실행</Btn>}>
      <Msg text={msg} /><Msg text={err} tone="error" />
      <Table testId="shipments-table" rows={data} cols={[
        { key: "order", label: "주문", render: (r) => <span>{r.order.product_title}<br /><span className="text-xs text-slate-500">{r.order.naver_product_order_id}</span></span> },
        { key: "supplier_code", label: "공급사" }, { key: "supplier_order_no", label: "발주번호" },
        { key: "carrier", label: "택배사(공급사→네이버)", render: (r) => r.carrier_code ? `${r.carrier_code} → ${r.naver_carrier_code || "매핑 없음"}` : "-" },
        { key: "tracking_no", label: "송장번호" },
        { key: "status", label: "주문 상태", render: (r) => <Badge value={r.order.status} /> },
        { key: "act", label: "송장 수동 입력", render: (r) => ["SUPPLIER_CONFIRMED", "SHIPPED"].includes(r.order.status) && (
          <div className="flex flex-wrap gap-1">
            <input placeholder="택배사 (CJ, 한진…)" className="w-28 rounded border px-1 text-xs" value={form[r.id]?.carrier || ""} onChange={(e) => setForm({ ...form, [r.id]: { ...form[r.id], carrier: e.target.value } })} />
            <input placeholder="송장번호" className="w-32 rounded border px-1 text-xs" value={form[r.id]?.no || ""} onChange={(e) => setForm({ ...form, [r.id]: { ...form[r.id], no: e.target.value } })} />
            <Btn onClick={() => act(() => api(`/purchases/${r.id}/tracking`, { method: "POST", body: { carrier_code: form[r.id]?.carrier, tracking_no: form[r.id]?.no } }), "송장 등록:")}>등록</Btn>
          </div>) },
      ]} />
    </Page>
  );
}
