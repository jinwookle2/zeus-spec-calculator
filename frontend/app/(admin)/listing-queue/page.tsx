"use client";

import { useState } from "react";
import { Badge, Btn, Filter, Msg, Page, Reasons, Table, useApi } from "@/components/ui";
import { api, pct, won } from "@/lib/api";

const PRICE_ONLY = (r: any) => (r.block_reasons || []).every((b: string) => /^(MARGIN_|PROFIT_|PRICE_ABOVE|CATEGORY_REQUIRED)/.test(b));

export default function ListingQueue() {
  const [status, setStatus] = useState("PENDING_APPROVAL,BLOCKED,FAILED,APPROVED");
  const { data, reload } = useApi<any[]>(`/products?status=${status || "PENDING_APPROVAL,BLOCKED,FAILED,APPROVED"}`);
  const [prices, setPrices] = useState<Record<number, string>>({});
  const [preview, setPreview] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [catQ, setCatQ] = useState("");
  const [catHits, setCatHits] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  async function act(fn: () => Promise<unknown>, ok: string) {
    try { await fn(); setMsg(ok); setErr(null); } catch (e) { setErr((e as Error).message); setMsg(null); }
    reload();
  }
  const approve = (p: any) => act(() => api(`/products/${p.id}/approve`, { method: "POST", body: prices[p.id] ? { sale_price: prices[p.id] } : {} }), `${p.listing_key} 승인 → 다음 등록 주기에 등록`);
  return (
    <Page title="상품 등록 대기" desc="AI 가공·정책 검증·마진 계산 결과. 최소 이익 조건을 충족하지 못하면 승인할 수 없습니다."
      actions={<>
        <Filter value={status} onChange={setStatus} options={["PENDING_APPROVAL", "BLOCKED", "FAILED", "APPROVED"]} />
        <Btn onClick={() => act(() => api("/jobs/publish_listings/run", { method: "POST" }), "승인 상품 등록 실행 완료")}>승인 상품 지금 등록</Btn>
      </>}>
      <Msg text={msg} /><Msg text={err} tone="error" />
      <Table testId="queue-table" rows={data} cols={[
        { key: "image", label: "", render: (r) => r.image ? <img src={r.image} alt="" className="h-12 w-12 rounded object-cover" /> : null },
        { key: "title", label: "가공 상품명", className: "min-w-[220px]", render: (r) => (
          <div><div className="font-medium">{r.title}</div><div className="text-xs text-slate-500">{r.listing_key} · {r.category_name || "카테고리 미지정"}</div>
            <div className="mt-1 flex flex-wrap gap-1">{(r.tags || []).map((t: string) => <span key={t} className="rounded bg-slate-100 px-1 text-xs">#{t}</span>)}</div>
            <div className="text-xs text-slate-400">AI: {r.ai_source}</div></div>) },
        { key: "supply", label: "공급가+배송", render: (r) => <span>{won(r.supply_price)}<br /><span className="text-xs text-slate-500">+{won(r.supplier_shipping_fee)}</span></span> },
        { key: "sale_price", label: "판매가", render: (r) => (
          <div className="space-y-1"><div>{won(r.sale_price)}</div>
            {r.status !== "APPROVED" && <input placeholder="가격 조정" className="w-24 rounded border px-1 py-0.5 text-xs" value={prices[r.id] || ""} onChange={(e) => setPrices({ ...prices, [r.id]: e.target.value })} />}</div>) },
        { key: "profit", label: "예상 이익/마진", render: (r) => <span>{won(r.expected_profit)}<br /><span className="text-xs">{pct(r.margin_rate)}</span></span> },
        { key: "status", label: "상태", render: (r) => <Badge value={r.status} /> },
        { key: "reasons", label: "차단 사유 / 경고", className: "min-w-[220px]", render: (r) => (
          <div><Reasons items={r.block_reasons} />{(r.warnings || []).map((w: string) => <div key={w} className="text-xs text-amber-700">⚠ {w}</div>)}
            {r.last_error && <div className="text-xs text-red-700">등록 오류: {r.last_error.slice(0, 160)}</div>}</div>) },
        { key: "act", label: "", render: (r) => (
          <div className="flex flex-col gap-1">
            {r.status !== "APPROVED" && (r.status !== "BLOCKED" || PRICE_ONLY(r)) && <Btn testId={`approve-${r.id}`} onClick={() => approve(r)}>승인</Btn>}
            {r.status !== "APPROVED" && <Btn tone="ghost" onClick={() => act(() => api(`/products/${r.id}/reprocess`, { method: "POST" }), "재가공 완료")}>재가공</Btn>}
            <Btn tone="ghost" onClick={async () => setPreview(await api(`/products/${r.id}`))}>상세</Btn>
            {r.status !== "BLOCKED" && r.status !== "APPROVED" && <Btn tone="danger" onClick={() => act(() => api(`/products/${r.id}/reject`, { method: "POST" }), "반려됨")}>반려</Btn>}
          </div>) },
      ]} />
      {preview && (
        <div className="fixed inset-0 z-10 flex items-center justify-center bg-black/40 p-4" onClick={() => setPreview(null)}>
          <div className="max-h-[90vh] w-full max-w-3xl overflow-auto rounded bg-white p-4" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex justify-between"><h3 className="font-semibold">{preview.title}</h3><Btn tone="ghost" onClick={() => setPreview(null)}>닫기</Btn></div>
            <h4 className="mt-2 text-sm font-semibold">카테고리: {preview.category_name || "미지정"} ({preview.category_id || "-"})</h4>
            {preview.status !== "APPROVED" && preview.status !== "LISTED" && (
              <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                <input placeholder="카테고리 검색 (예: 텀블러)" className="rounded border px-2 py-1" value={catQ} onChange={(e) => setCatQ(e.target.value)} />
                <Btn tone="ghost" onClick={async () => setCatHits((await api(`/categories?q=${encodeURIComponent(catQ)}`)).items)}>검색</Btn>
                {catHits.map((c) => (
                  <button key={c.id} className="rounded bg-slate-100 px-2 py-0.5 hover:bg-slate-200" onClick={async () => {
                    await act(() => api(`/products/${preview.id}`, { method: "PATCH", body: { category_id: c.id, category_name: c.whole_name } }), "카테고리 변경");
                    setPreview(await api(`/products/${preview.id}`)); setCatHits([]);
                  }}>{c.whole_name}</button>))}
              </div>)}
            <h4 className="mt-2 text-sm font-semibold">상세페이지 미리보기</h4>
            <iframe title="detail" sandbox="" className="h-96 w-full rounded border" srcDoc={preview.detail_html} />
            <h4 className="mt-3 text-sm font-semibold">가격 구성</h4>
            <pre className="overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(preview.cost_breakdown, null, 2)}</pre>
            <h4 className="mt-3 text-sm font-semibold">고시정보</h4>
            <pre className="overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(preview.notice, null, 2)}</pre>
            <h4 className="mt-3 text-sm font-semibold">API 호출 기록</h4>
            <pre className="overflow-auto rounded bg-slate-50 p-2 text-xs">{JSON.stringify(preview.api_logs?.map((l: any) => ({ action: l.action, success: l.success, dry_run: l.dry_run, error: l.error, response: l.response })), null, 2)}</pre>
          </div>
        </div>
      )}
    </Page>
  );
}
