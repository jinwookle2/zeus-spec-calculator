"use client";

import { useState } from "react";
import { Badge, Btn, Card, Filter, Msg, Page, Stat, Table, useApi } from "@/components/ui";
import { api, pct, won } from "@/lib/api";

export default function Analytics() {
  const [days, setDays] = useState("30");
  const { data, reload } = useApi(`/analytics/revenue?days=${days || 30}`);
  const [mismatchOnly, setMismatchOnly] = useState(false);
  const st = useApi<any[]>(`/settlements${mismatchOnly ? "?mismatch_only=true" : ""}`);
  const [msg, setMsg] = useState<string | null>(null);
  async function reconcile() {
    try { setMsg("정산 대사: " + JSON.stringify(await api("/jobs/reconcile_settlements/run", { method: "POST" }))); }
    catch (e) { setMsg((e as Error).message); }
    st.reload(); reload();
  }
  const byDay = Object.entries((data?.by_day || {}) as Record<string, string>);
  const max = Math.max(1, ...byDay.map(([, v]) => Number(v)));
  return (
    <Page title="매출 및 수익 분석" desc={data?.fee_basis ? `${data.fee_basis}. ${data.note}` : data?.note}
      actions={<><Filter value={days} onChange={setDays} options={["7", "30", "90", "365"]} /><Btn testId="reconcile" onClick={reconcile}>정산 대사 실행</Btn></>}>
      <Msg text={msg} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="주문 수" value={data?.orders ?? 0} />
        <Stat label="매출" value={won(data?.sales)} />
        <Stat label="예상 이익" value={won(data?.estimated_profit)} tone="green" />
        <Stat label="이익률" value={pct(data?.margin_rate)} />
      </div>
      <Card title="비용 구성">
        <dl className="grid grid-cols-2 gap-1 text-sm md:grid-cols-4">
          <dt>플랫폼 수수료</dt><dd>{won(data?.platform_fees)}</dd><dt>광고비</dt><dd>{won(data?.ad_cost)}</dd>
          <dt>공급사 발주액</dt><dd>{won(data?.supplier_cost)}</dd><dt>기타 변동비</dt><dd>{won(data?.other_cost)}</dd>
        </dl>
      </Card>
      <Card title="일별 매출">
        {byDay.length === 0 ? <p className="text-sm text-slate-400">데이터 없음</p> : (
          <div className="flex h-48 items-end gap-1 overflow-x-auto">
            {byDay.map(([d, v]) => (
              <div key={d} className="flex min-w-[28px] flex-1 flex-col items-center gap-1" title={`${d}: ${won(v)}`}>
                <div className="w-full rounded-t bg-slate-700" style={{ height: `${(Number(v) / max) * 160}px` }} />
                <span className="text-[10px] text-slate-500">{d.slice(5)}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
      <Card title="네이버 정산 내역 · 수수료 대사">
        <label className="mb-2 block text-xs"><input type="checkbox" checked={mismatchOnly} onChange={(e) => setMismatchOnly(e.target.checked)} /> 불일치만 보기</label>
        <Table testId="settlements-table" rows={st.data} empty="정산 내역 없음 (정산 대사 실행)" cols={[
          { key: "product_order_id", label: "상품주문번호" }, { key: "settle_type", label: "정산 구분" },
          { key: "settle_basis_date", label: "정산 기준일" }, { key: "settle_expect_date", label: "정산 예정일" },
          { key: "pay_settle_amount", label: "결제금액", render: (r) => won(r.pay_settle_amount) },
          { key: "commission_amount", label: "실제 수수료", render: (r) => won(r.commission_amount) },
          { key: "expected_commission", label: "설정 기준 추정", render: (r) => won(r.expected_commission) },
          { key: "commission_diff", label: "차이", render: (r) => <span className={r.mismatch ? "font-semibold text-red-600" : ""}>{won(r.commission_diff)}</span> },
          { key: "settle_expect_amount", label: "정산 예정액", render: (r) => won(r.settle_expect_amount) },
          { key: "mismatch", label: "대사", render: (r) => <Badge value={r.mismatch ? "FAILED" : "ACTIVE"} /> },
        ]} />
      </Card>
    </Page>
  );
}
