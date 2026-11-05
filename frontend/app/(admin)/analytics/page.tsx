"use client";

import { useState } from "react";
import { Card, Filter, Page, Stat, useApi } from "@/components/ui";
import { pct, won } from "@/lib/api";

export default function Analytics() {
  const [days, setDays] = useState("30");
  const { data } = useApi(`/analytics/revenue?days=${days || 30}`);
  const byDay = Object.entries((data?.by_day || {}) as Record<string, string>);
  const max = Math.max(1, ...byDay.map(([, v]) => Number(v)));
  return (
    <Page title="매출 및 수익 분석" desc={data?.note} actions={<Filter value={days} onChange={setDays} options={["7", "30", "90", "365"]} />}>
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
    </Page>
  );
}
