"use client";

import { useState } from "react";
import { Badge, Btn, Msg, Page, Table, useApi } from "@/components/ui";
import { api, dt } from "@/lib/api";

const ROLES = ["viewer", "operator", "admin"];

export default function Users() {
  const { data, error, reload } = useApi<any[]>("/users");
  const [form, setForm] = useState({ email: "", password: "", role: "viewer" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function act(fn: () => Promise<unknown>, ok: string) {
    try { await fn(); setMsg(ok); setErr(null); } catch (e) { setErr((e as Error).message); setMsg(null); }
    reload();
  }
  const patch = (u: any, body: object, ok: string) => act(() => api(`/users/${u.id}`, { method: "PATCH", body }), ok);
  return (
    <Page title="사용자 관리" desc="admin 전용. viewer: 조회 / operator: 승인·발주·송장 / admin: 설정·사용자·개인정보 열람. 모든 변경은 감사 로그에 기록됩니다.">
      <Msg text={msg} /><Msg text={err || (error?.includes("admin") ? "admin 권한이 필요합니다" : error)} tone="error" />
      <Table testId="users-table" rows={data} cols={[
        { key: "email", label: "이메일" },
        { key: "role", label: "역할", render: (u) => (
          <select className="rounded border px-1 py-0.5 text-xs" value={u.role} onChange={(e) => patch(u, { role: e.target.value }, `${u.email} 역할 변경`)}>
            {ROLES.map((r) => <option key={r}>{r}</option>)}
          </select>) },
        { key: "active", label: "상태", render: (u) => <Badge value={u.active ? "ACTIVE" : "SUSPENDED"} /> },
        { key: "totp_enabled", label: "2FA", render: (u) => (u.totp_enabled ? "사용" : "-") },
        { key: "locked_until", label: "잠금", render: (u) => (u.locked_until && new Date(u.locked_until) > new Date() ? <span className="text-red-600">{dt(u.locked_until)}까지</span> : "-") },
        { key: "password_changed_at", label: "비밀번호 변경", render: (u) => (u.password_changed_at ? dt(u.password_changed_at) : <span className="text-amber-700">초기/재설정</span>) },
        { key: "act", label: "", render: (u) => (
          <div className="flex flex-wrap gap-1">
            <Btn tone="ghost" onClick={() => patch(u, { active: !u.active }, u.active ? "비활성화" : "활성화")}>{u.active ? "비활성화" : "활성화"}</Btn>
            <Btn tone="ghost" onClick={() => patch(u, { unlock: true }, "잠금 해제")}>잠금 해제</Btn>
            {u.totp_enabled && <Btn tone="ghost" onClick={() => patch(u, { reset_2fa: true }, "2FA 초기화")}>2FA 초기화</Btn>}
          </div>) },
      ]} />
      <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
        <h2 className="mb-2 font-semibold">사용자 추가</h2>
        <div className="flex flex-wrap gap-2">
          <input placeholder="이메일" className="rounded border px-2 py-1" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <input placeholder="초기 비밀번호 (10자 이상)" type="password" className="rounded border px-2 py-1" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <select className="rounded border px-2 py-1" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{ROLES.map((r) => <option key={r}>{r}</option>)}</select>
          <Btn testId="add-user" onClick={() => act(() => api("/users", { method: "POST", body: form }), `${form.email} 추가`)}>추가</Btn>
        </div>
      </div>
    </Page>
  );
}
