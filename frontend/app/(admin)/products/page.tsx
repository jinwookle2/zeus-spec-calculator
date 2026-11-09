"use client";

import { useState } from "react";
import { Badge, Btn, Msg, Page, Table, useApi } from "@/components/ui";
import { api, dt, pct, won } from "@/lib/api";

export default function Products() {
  const { data, reload } = useApi<any[]>("/products?status=LISTED,SOLD_OUT,SUSPENDED");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function act(fn: () => Promise<unknown>, ok: string) {
    try { await fn(); setMsg(ok); setErr(null); } catch (e) { setErr((e as Error).message); }
    reload();
  }
  return (
    <Page title="등록 상품 관리" desc="스마트스토어에 등록된 상품. 판매중지/재개, 주문 시뮬레이션(Mock 모드)을 할 수 있습니다.">
      <Msg text={msg} /><Msg text={err} tone="error" />
      <Table testId="products-table" rows={data} cols={[
        { key: "title", label: "상품명", className: "min-w-[220px]" },
        { key: "naver_origin_product_no", label: "네이버 원상품번호", render: (r) => <span>{r.naver_origin_product_no}{r.dry_run_listed && <span className="ml-1 rounded bg-amber-100 px-1 text-xs text-amber-800">DRY-RUN</span>}</span> },
        { key: "sale_price", label: "판매가", render: (r) => won(r.sale_price) },
        { key: "margin_rate", label: "마진", render: (r) => pct(r.margin_rate) },
        { key: "stock", label: "재고(네이버/공급사)", render: (r) => `${r.stock} / ${r.supplier_stock}` },
        { key: "status", label: "상태", render: (r) => <Badge value={r.status} /> },
        { key: "listed_at", label: "등록일", render: (r) => dt(r.listed_at) },
        { key: "act", label: "", render: (r) => (
          <div className="flex flex-wrap gap-1">
            {r.status === "LISTED" && <Btn tone="danger" onClick={() => act(() => api(`/products/${r.id}/suspend`, { method: "POST" }), "판매중지")}>판매중지</Btn>}
            {r.status === "SUSPENDED" && <Btn onClick={() => act(() => api(`/products/${r.id}/resume`, { method: "POST" }), "판매재개")}>재개</Btn>}
            {r.status === "LISTED" && <Btn tone="ghost" testId={`mock-order-${r.id}`} onClick={() => act(() => api("/mock/orders", { method: "POST", body: { product_id: r.id, quantity: 1 } }), "Mock 주문 생성 → 주문 관리에서 '주문 수집' 실행")}>Mock 주문</Btn>}
          </div>) },
      ]} />
    </Page>
  );
}
