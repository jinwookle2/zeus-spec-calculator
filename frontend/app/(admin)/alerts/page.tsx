"use client";

import { useState } from "react";
import { Badge, Btn, Card, Page, Table, useApi } from "@/components/ui";
import { api, dt } from "@/lib/api";

export default function Alerts() {
  const alerts = useApi<any[]>("/alerts");
  const dlq = useApi<any[]>("/dead-letters");
  const logs = useApi<any[]>("/api-logs");
  const [tab, setTab] = useState("alerts");
  const tabs = [["alerts", "알림"], ["dlq", "Dead Letter Queue"], ["logs", "외부 API 호출 기록"]];
  return (
    <Page title="오류 및 알림" desc="재고 불일치, 발주 실패, 등록 실패, 발송처리 실패 등. ALERT_WEBHOOK_URL 설정 시 외부로도 전송됩니다.">
      <div className="flex gap-2">{tabs.map(([k, l]) => <Btn key={k} tone={tab === k ? "primary" : "ghost"} onClick={() => setTab(k)}>{l}</Btn>)}</div>
      {tab === "alerts" && <Table testId="alerts-table" rows={alerts.data} cols={[
        { key: "level", label: "레벨", render: (r) => <Badge value={r.level} /> }, { key: "category", label: "분류" },
        { key: "message", label: "내용", className: "min-w-[260px]" }, { key: "created_at", label: "시각", render: (r) => dt(r.created_at) },
        { key: "act", label: "", render: (r) => r.acknowledged ? <span className="text-xs text-slate-400">확인됨</span> :
          <Btn tone="ghost" onClick={async () => { await api(`/alerts/${r.id}/ack`, { method: "POST" }); alerts.reload(); }}>확인</Btn> },
      ]} />}
      {tab === "dlq" && <Table rows={dlq.data} cols={[
        { key: "task_name", label: "작업" }, { key: "payload", label: "payload", render: (r) => <code className="text-xs">{JSON.stringify(r.payload)}</code> },
        { key: "error", label: "오류", className: "text-xs text-red-700" }, { key: "attempts", label: "시도" },
        { key: "act", label: "", render: (r) => r.resolved ? "해결" : <Btn tone="ghost" onClick={async () => { await api(`/dead-letters/${r.id}/resolve`, { method: "POST" }); dlq.reload(); }}>해결 처리</Btn> },
      ]} />}
      {tab === "logs" && <Card><Table rows={logs.data} cols={[
        { key: "action", label: "API" }, { key: "entity_id", label: "대상" },
        { key: "success", label: "성공", render: (r) => <Badge value={r.success ? "ACTIVE" : "FAILED"} /> },
        { key: "dry_run", label: "Dry-run", render: (r) => r.dry_run ? "예" : "" },
        { key: "error", label: "오류/메모", className: "text-xs" }, { key: "created_at", label: "시각", render: (r) => dt(r.created_at) },
      ]} /></Card>}
    </Page>
  );
}
