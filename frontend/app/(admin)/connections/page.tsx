"use client";

import { useState } from "react";
import { Btn, Card, Msg, Page, useApi } from "@/components/ui";
import { api } from "@/lib/api";

const Row = ({ k, v }: { k: string; v: unknown }) => (
  <div className="flex justify-between border-b border-slate-100 py-1 text-sm"><span className="text-slate-600">{k}</span>
    <span className={typeof v === "boolean" ? (v ? "font-semibold text-emerald-700" : "text-slate-500") : ""}>{typeof v === "boolean" ? (v ? "ON / 설정됨" : "OFF / 미설정") : String(v)}</span></div>
);

export default function Connections() {
  const { data } = useApi("/connections");
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <Page title="API 연결 설정" desc={data?.note} actions={<Btn onClick={async () => setMsg(JSON.stringify(await api("/connections/naver/test", { method: "POST" })))}>네이버 연결 테스트</Btn>}>
      <Msg text={msg} />
      <div className="grid gap-3 lg:grid-cols-2">
        <Card title="네이버 커머스 API">{data && Object.entries(data.naver).map(([k, v]) => <Row key={k} k={k} v={v} />)}</Card>
        <Card title="안전 스위치 (환경변수)">{data && Object.entries(data.safety).map(([k, v]) => <Row key={k} k={k} v={v} />)}
          <p className="mt-2 text-xs text-slate-500">ALLOW_PUBLIC_LISTING / ALLOW_REAL_PURCHASE / ALLOW_PII_TRANSFER / ALLOW_NAVER_ORDER_ACTIONS 를 true 로 바꾸기 전에는 실제 등록·결제·개인정보 전송·발송처리가 실행되지 않고 Dry-run 으로 기록됩니다.</p></Card>
        <Card title="Claude API">{data && Object.entries(data.claude).map(([k, v]) => <Row key={k} k={k} v={v} />)}</Card>
        <Card title="모니터링">{data && Object.entries(data.monitoring).map(([k, v]) => <Row key={k} k={k} v={v} />)}</Card>
      </div>
    </Page>
  );
}
