"use client";

import { useState } from "react";
import { Badge, Btn, Msg, Page, Table, useApi } from "@/components/ui";
import { api } from "@/lib/api";

export default function Inventory() {
  const { data, reload } = useApi<any[]>("/inventory");
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <Page title="재고 관리" desc="공급사 재고 → 네이버 재고 동기화. 품절 시 자동 품절 처리, 공급가 상승으로 최소 이익 미달 시 판매중지."
      actions={<Btn testId="sync-inventory" onClick={async () => { setMsg(JSON.stringify(await api("/jobs/sync_inventory/run", { method: "POST" }))); reload(); }}>재고 동기화 실행</Btn>}>
      <Msg text={msg} />
      <Table rows={data} cols={[
        { key: "listing_key", label: "상품키" }, { key: "title", label: "상품명", className: "min-w-[200px]" },
        { key: "stock", label: "네이버 재고" }, { key: "supplier_stock", label: "공급사 재고" },
        { key: "mismatch", label: "불일치", render: (r) => r.mismatch ? <span className="text-red-600">불일치</span> : "-" },
        { key: "status", label: "상태", render: (r) => <Badge value={r.status} /> },
        { key: "last_error", label: "비고", render: (r) => <span className="text-xs text-red-700">{r.last_error || ""}</span> },
      ]} />
    </Page>
  );
}
