"use client";

import { useState } from "react";
import { Btn, Card, Msg, Page } from "@/components/ui";
import { api } from "@/lib/api";

export default function Account() {
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  async function save() {
    if (form.next !== form.confirm) { setErr("새 비밀번호가 서로 다릅니다"); return; }
    try {
      await api("/auth/password", { method: "POST", body: { current_password: form.current, new_password: form.next } });
      setMsg("비밀번호를 변경했습니다"); setErr(null); setForm({ current: "", next: "", confirm: "" });
    } catch (e) { setErr((e as Error).message); setMsg(null); }
  }
  return (
    <Page title="내 계정" desc="로그인 5회 실패 시 15분간 잠깁니다. 비밀번호는 10자 이상.">
      <Msg text={msg} /><Msg text={err} tone="error" />
      <Card title="비밀번호 변경" className="max-w-md">
        <div className="space-y-2 text-sm">
          {([["current", "현재 비밀번호"], ["next", "새 비밀번호"], ["confirm", "새 비밀번호 확인"]] as const).map(([k, l]) => (
            <label key={k} className="block">{l}
              <input data-testid={`pw-${k}`} type="password" className="mt-1 w-full rounded border px-2 py-1" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
            </label>))}
          <Btn testId="pw-save" onClick={save}>변경</Btn>
        </div>
      </Card>
    </Page>
  );
}
