"use client";

import { useState } from "react";
import { Badge, Btn, Filter, Msg, Page, Table, useApi } from "@/components/ui";
import { api, dt, won } from "@/lib/api";

export default function Purchases() {
  const [status, setStatus] = useState("");
  const { data, reload } = useApi<any[]>(`/purchases${status ? `?status=${status}` : ""}`);
  const [manualNo, setManualNo] = useState<Record<number, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function act(fn: () => Promise<any>, ok: string) {
    try { const r = await fn(); setMsg(`${ok} ${r?.result ?? ""}`); setErr(null); } catch (e) { setErr((e as Error).message); }
    reload();
  }
  return (
    <Page title="공급사 발주" desc="자동 발주가 허용되지 않은 공급사/발주 API가 없는 공급사의 주문은 여기서 승인합니다. 동일 주문은 1건만 발주됩니다."
      actions={<>
        <Filter value={status} onChange={setStatus} options={["PENDING_APPROVAL", "REQUESTING", "REQUESTED", "CONFIRMED", "SHIPPED", "FAILED", "CANCELLED"]} />
        <Btn onClick={() => act(() => api("/jobs/retry_purchases/run", { method: "POST" }), "재시도 실행")}>실패 발주 재시도</Btn>
      </>}>
      <Msg text={msg} /><Msg text={err} tone="error" />
      <Table testId="purchases-table" rows={data} cols={[
        { key: "idempotency_key", label: "멱등키" }, { key: "supplier_code", label: "공급사" },
        { key: "order", label: "주문", render: (r) => <span>{r.order.product_title}<br /><span className="text-xs text-slate-500">{r.order.naver_product_order_id} · {r.order.quantity}개</span></span> },
        { key: "amount", label: "발주액", render: (r) => won(r.amount) },
        { key: "status", label: "발주 상태", render: (r) => <div><Badge value={r.status} />{r.dry_run && <span className="ml-1 rounded bg-amber-100 px-1 text-xs">DRY-RUN</span>}</div> },
        { key: "order_status", label: "주문 상태", render: (r) => <Badge value={r.order.status} /> },
        { key: "supplier_order_no", label: "공급사 발주번호", render: (r) => <span>{r.supplier_order_no || "-"}{r.return_status && <span className="block text-xs text-orange-700">반품 {r.return_status} {r.supplier_return_no || ""}</span>}</span> }, { key: "attempts", label: "시도" },
        { key: "last_error", label: "오류", render: (r) => <span className="text-xs text-red-700">{r.last_error || ""}</span> },
        { key: "created_at", label: "생성", render: (r) => dt(r.created_at) },
        { key: "act", label: "", render: (r) => ["AWAITING_APPROVAL", "ON_HOLD", "STOCK_CHECKED"].includes(r.order.status) && (
          <div className="flex flex-col gap-1">
            <Btn testId={`approve-po-${r.id}`} onClick={() => act(() => api(`/purchases/${r.id}/approve`, { method: "POST", body: {} }), "발주 승인:")}>API 발주 승인</Btn>
            <input placeholder="수동 발주번호" className="w-32 rounded border px-1 text-xs" value={manualNo[r.id] || ""} onChange={(e) => setManualNo({ ...manualNo, [r.id]: e.target.value })} />
            <Btn tone="ghost" disabled={!manualNo[r.id]} onClick={() => act(() => api(`/purchases/${r.id}/approve`, { method: "POST", body: { supplier_order_no: manualNo[r.id] } }), "수동 발주 기록:")}>수동 발주 완료</Btn>
          </div>) },
      ]} />
    </Page>
  );
}
