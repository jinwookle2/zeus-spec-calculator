"use client";

import { useState } from "react";
import { Btn, Card, Msg, Page, Stat, Table, Badge, useApi } from "@/components/ui";
import { api, won, pct, dt } from "@/lib/api";

export default function Dashboard() {
  const { data, reload } = useApi("/dashboard");
  const runs = useApi<any[]>("/job-runs");
  const [msg, setMsg] = useState<string | null>(null);
  async function runPipeline() {
    setMsg("전체 파이프라인 실행 중…");
    try {
      await api("/jobs/pipeline/run", { method: "POST" });
      setMsg("전체 파이프라인 실행 완료");
    } catch (e) {
      setMsg((e as Error).message);
    }
    reload();
    runs.reload();
  }
  const rev = data?.revenue_30d;
  return (
    <Page title="대시보드" desc="전체 운영 현황" actions={<Btn testId="run-pipeline" onClick={runPipeline}>전체 파이프라인 지금 실행</Btn>}>
      <Msg text={msg} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="등록 상품" value={data?.products?.LISTED ?? 0} />
        <Stat label="등록 대기 (승인 필요)" value={data?.products?.PENDING_APPROVAL ?? 0} tone="amber" />
        <Stat label={`오늘 등록 / 한도`} value={`${data?.listed_today ?? 0} / ${data?.daily_listing_limit ?? "-"}`} />
        <Stat label="등록 차단" value={data?.products?.BLOCKED ?? 0} tone="red" />
        <Stat label="발주 승인 대기" value={data?.awaiting_purchase_approval ?? 0} tone="amber" />
        <Stat label="보류 주문" value={data?.on_hold ?? 0} tone="red" />
        <Stat label="미확인 알림" value={data?.open_alerts ?? 0} tone="red" />
        <Stat label="DLQ" value={data?.dead_letters ?? 0} tone="red" />
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <Card title="최근 30일 (추정)">
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <dt>주문 수</dt><dd className="text-right">{rev?.orders ?? 0}건</dd>
            <dt>매출</dt><dd className="text-right">{won(rev?.sales)}</dd>
            <dt>예상 이익</dt><dd className="text-right font-semibold">{won(rev?.estimated_profit)}</dd>
            <dt>이익률</dt><dd className="text-right">{pct(rev?.margin_rate)}</dd>
          </dl>
        </Card>
        <Card title="주문 상태">
          <div className="flex flex-wrap gap-2 text-sm">
            {Object.entries(data?.orders || {}).map(([k, v]) => <span key={k} className="flex items-center gap-1"><Badge value={k} />{String(v)}</span>)}
            {!data?.orders || Object.keys(data.orders).length === 0 ? <span className="text-slate-400">주문 없음</span> : null}
          </div>
        </Card>
      </div>
      <Card title="최근 작업 실행">
        <Table rows={(runs.data || []).slice(0, 12)} cols={[
          { key: "job", label: "작업" },
          { key: "success", label: "결과", render: (r) => <Badge value={r.success ? "ACTIVE" : "FAILED"} /> },
          { key: "summary", label: "요약", render: (r) => <code className="text-xs">{JSON.stringify(r.summary).slice(0, 140)}</code> },
          { key: "started_at", label: "시작", render: (r) => dt(r.started_at) },
        ]} />
      </Card>
    </Page>
  );
}
