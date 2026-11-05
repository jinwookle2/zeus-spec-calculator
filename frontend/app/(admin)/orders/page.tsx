"use client";

import { useState } from "react";
import { Badge, Btn, Filter, Msg, Page, Table, useApi } from "@/components/ui";
import { api, dt, getRole, won } from "@/lib/api";

const STATES = ["PAID", "STOCK_CHECKED", "AWAITING_APPROVAL", "PURCHASE_REQUESTED", "SUPPLIER_CONFIRMED", "SHIPPED",
  "TRACKING_REGISTERED", "DELIVERED", "ON_HOLD", "CANCEL_REQUESTED", "CANCELLED", "RETURN_REQUESTED", "RETURNED", "FAILED"];

export default function Orders() {
  const [status, setStatus] = useState("");
  const { data, reload } = useApi<any[]>(`/orders${status ? `?status=${status}` : ""}`);
  const [detail, setDetail] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function act(fn: () => Promise<any>, ok: string) {
    try { const r = await fn(); setMsg(`${ok} ${r ? JSON.stringify(r).slice(0, 200) : ""}`); setErr(null); } catch (e) { setErr((e as Error).message); }
    reload();
  }
  const open = async (id: number, reveal = false) => setDetail(await api(`/orders/${id}${reveal ? "?reveal=true" : ""}`));
  return (
    <Page title="주문 관리" desc="PAID → STOCK_CHECKED → PURCHASE_REQUESTED → SUPPLIER_CONFIRMED → SHIPPED → TRACKING_REGISTERED → DELIVERED"
      actions={<>
        <Filter value={status} onChange={setStatus} options={STATES} />
        <Btn testId="collect-orders" onClick={() => act(() => api("/jobs/collect_orders/run", { method: "POST" }), "주문 수집:")}>주문 수집</Btn>
        <Btn testId="process-orders" onClick={() => act(() => api("/jobs/process_orders/run", { method: "POST" }), "재고확인/발주:")}>재고 확인·발주 처리</Btn>
      </>}>
      <Msg text={msg} /><Msg text={err} tone="error" />
      <Table testId="orders-table" rows={data} cols={[
        { key: "naver_product_order_id", label: "상품주문번호" }, { key: "product_title", label: "상품", className: "min-w-[180px]" },
        { key: "option_text", label: "옵션" }, { key: "quantity", label: "수량" },
        { key: "total_amount", label: "결제액", render: (r) => won(r.total_amount) },
        { key: "buyer", label: "수령인", render: (r) => <span className="text-xs">{r.buyer?.name} / {r.buyer?.phone}</span> },
        { key: "status", label: "상태", render: (r) => <div><Badge value={r.status} />{r.hold_reason && <div className="max-w-xs text-xs text-orange-700">{r.hold_reason}</div>}</div> },
        { key: "created_at", label: "수집", render: (r) => dt(r.created_at) },
        { key: "act", label: "", render: (r) => (
          <div className="flex flex-col gap-1">
            <Btn tone="ghost" onClick={() => open(r.id)}>이력</Btn>
            {r.status === "ON_HOLD" && <Btn onClick={() => act(() => api(`/orders/${r.id}/release-hold`, { method: "POST" }), "보류 해제")}>보류 해제</Btn>}
            {["PAID", "STOCK_CHECKED", "AWAITING_APPROVAL", "ON_HOLD", "SUPPLIER_CONFIRMED", "CANCEL_REQUESTED"].includes(r.status) &&
              <Btn tone="danger" onClick={() => act(() => api(`/orders/${r.id}/cancel`, { method: "POST" }), "취소 처리:")}>취소</Btn>}
            {r.status === "RETURN_REQUESTED" && <Btn onClick={() => act(() => api(`/orders/${r.id}/approve-return`, { method: "POST" }), "반품 승인")}>반품 승인</Btn>}
          </div>) },
      ]} />
      {detail && (
        <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/40 p-4" onClick={() => setDetail(null)}>
          <div className="max-h-[90vh] w-full max-w-2xl overflow-auto rounded bg-white p-4 text-sm" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex justify-between"><h3 className="font-semibold">주문 {detail.naver_product_order_id}</h3><Btn tone="ghost" onClick={() => setDetail(null)}>닫기</Btn></div>
            <p>수령인: {detail.buyer?.name} / {detail.buyer?.phone} / {detail.buyer?.address}
              {getRole() === "admin" && <button className="ml-2 text-xs underline" onClick={() => open(detail.id, true)}>개인정보 열람(감사기록)</button>}</p>
            <h4 className="mt-3 font-semibold">상태 변경 감사 로그</h4>
            <ol className="mt-1 space-y-1">{detail.events.map((e: any) => (
              <li key={e.id} className="text-xs"><Badge value={e.to_status} /> {dt(e.created_at)} · {e.actor} · {e.reason}</li>))}</ol>
            <h4 className="mt-3 font-semibold">발주</h4>
            <pre className="overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(detail.purchase, null, 2)}</pre>
          </div>
        </div>
      )}
    </Page>
  );
}
