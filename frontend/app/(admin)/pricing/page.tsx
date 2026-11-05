"use client";

import { Fragment, useState } from "react";
import { Btn, Card, Msg, Page, Table, useApi } from "@/components/ui";
import { api, pct, won } from "@/lib/api";

export default function Pricing() {
  const settings = useApi("/settings");
  const products = useApi<any[]>("/products");
  const [sim, setSim] = useState({ supply_price: "10000", shipping_fee: "3000", sale_price: "" });
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  async function run() {
    try {
      setRes(await api("/pricing/simulate", { method: "POST", body: { supply_price: sim.supply_price, shipping_fee: sim.shipping_fee, sale_price: sim.sale_price || null } }));
      setErr(null);
    } catch (e) { setErr((e as Error).message); }
  }
  const s = settings.data;
  const fees = s?.platform_fee_rates || {};
  return (
    <Page title="가격 및 마진 관리" desc="판매가 − 공급가 − 공급사 배송비 − 플랫폼 수수료 − 광고비 배분 − 기타 변동비 = 예상 이익">
      <div className="grid gap-3 lg:grid-cols-2">
        <Card title="현재 가격 정책 (자동화 설정에서 변경)">
          <dl className="grid grid-cols-2 gap-1 text-sm">
            <dt>목표 마진율</dt><dd>{pct(s?.target_margin_rate)}</dd>
            <dt>최소 이익금</dt><dd>{won(s?.min_profit_krw)}</dd>
            {Object.entries(fees).map(([k, v]) => <Fragment key={k}><dt>{k}</dt><dd>{pct(v as number)}</dd></Fragment>)}
            <dt>광고비 배분</dt><dd>{pct(s?.ad_cost_rate)} + {won(s?.ad_cost_per_order)}/주문</dd>
            <dt>기타 변동비</dt><dd>{won(s?.other_variable_cost)}/주문</dd>
            <dt>고객 배송비</dt><dd>{won(s?.customer_shipping_fee)}</dd>
          </dl>
          <p className="mt-2 text-xs text-amber-700">⚠ 수수료 기본값은 예시입니다. 실제 계약 수수료로 수정하세요.</p>
        </Card>
        <Card title="가격 시뮬레이터">
          <div className="flex flex-wrap gap-2 text-sm">
            <label>공급가 <input className="w-24 rounded border px-1" value={sim.supply_price} onChange={(e) => setSim({ ...sim, supply_price: e.target.value })} /></label>
            <label>공급사 배송비 <input className="w-20 rounded border px-1" value={sim.shipping_fee} onChange={(e) => setSim({ ...sim, shipping_fee: e.target.value })} /></label>
            <label>판매가(선택) <input className="w-24 rounded border px-1" value={sim.sale_price} onChange={(e) => setSim({ ...sim, sale_price: e.target.value })} /></label>
            <Btn testId="simulate" onClick={run}>계산</Btn>
          </div>
          <Msg text={err} tone="error" />
          {res && (["suggested", "evaluated"] as const).filter((k) => res[k]).map((k) => (
            <div key={k} className="mt-3 text-sm" data-testid={`sim-${k}`}>
              <div className="font-semibold">{k === "suggested" ? "권장 판매가" : "입력 판매가 평가"}: {won(res[k].sale_price)} {res[k].ok ? "✅" : "⛔"}</div>
              <div>예상 이익 {won(res[k].expected_profit)} · 마진 {pct(res[k].margin_rate)} · 수수료 {won(res[k].platform_fee)} · 광고비 {won(res[k].ad_cost)} · 원가 {won(res[k].supply_cost)}</div>
              {res[k].reasons?.map((r: string) => <div key={r} className="text-xs text-red-700">{r}</div>)}
            </div>
          ))}
        </Card>
      </div>
      <Table rows={products.data} cols={[
        { key: "listing_key", label: "상품키" }, { key: "title", label: "상품명", className: "min-w-[200px]" },
        { key: "supply_price", label: "공급가", render: (r) => won(r.supply_price) },
        { key: "sale_price", label: "판매가", render: (r) => won(r.sale_price) },
        { key: "expected_profit", label: "예상 이익", render: (r) => won(r.expected_profit) },
        { key: "margin_rate", label: "마진", render: (r) => <span className={Number(r.margin_rate) < Number(s?.target_margin_rate) ? "text-red-600" : ""}>{pct(r.margin_rate)}</span> },
        { key: "status", label: "상태" },
      ]} />
    </Page>
  );
}
