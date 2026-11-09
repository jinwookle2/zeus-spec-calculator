"use client";

import { useState } from "react";
import { Badge, Filter, Page, Table, useApi } from "@/components/ui";
import { won } from "@/lib/api";

export default function Sourcing() {
  const [status, setStatus] = useState("");
  const { data } = useApi<any[]>(`/sourcing${status ? `?status=${status}` : ""}`);
  return (
    <Page title="상품 소싱" desc="공급사 API/승인된 피드에서 수집된 원본 상품. 중복·품절·단종 상품은 가공 대상에서 제외됩니다."
      actions={<Filter value={status} onChange={setStatus} options={["ACTIVE", "SOLD_OUT", "DUPLICATE", "DISCONTINUED"]} />}>
      <Table testId="sourcing-table" rows={data} cols={[
        { key: "img", label: "", render: (r) => r.images?.[0] ? <img src={r.images[0]} alt="" className="h-10 w-10 rounded object-cover" /> : null },
        { key: "supplier_code", label: "공급사" }, { key: "supplier_sku", label: "공급사 상품코드" },
        { key: "name", label: "상품명", className: "min-w-[220px]" }, { key: "brand", label: "브랜드" },
        { key: "supply_price", label: "공급가", render: (r) => won(r.supply_price) },
        { key: "shipping_fee", label: "배송비", render: (r) => won(r.shipping_fee) },
        { key: "stock", label: "재고" }, { key: "options", label: "옵션", render: (r) => (r.options || []).length },
        { key: "status", label: "상태", render: (r) => <Badge value={r.status} /> },
        { key: "product_status", label: "가공 결과", render: (r) => <Badge value={r.product_status} /> },
      ]} />
    </Page>
  );
}
