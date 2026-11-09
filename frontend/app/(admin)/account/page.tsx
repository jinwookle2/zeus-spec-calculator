"use client";

import { useState } from "react";
import { Btn, Card, Msg, Page, useApi } from "@/components/ui";
import { api } from "@/lib/api";

export default function Account() {
  const [form, setForm] = useState({ current: "", next: "", confirm: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const me = useApi("/auth/me");
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [pw, setPw] = useState("");
  async function run(fn: () => Promise<unknown>, ok: string) {
    try { await fn(); setMsg(ok); setErr(null); } catch (e) { setErr((e as Error).message); setMsg(null); }
    me.reload();
  }
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
      <Card title={`2단계 인증 (OTP): ${me.data?.totp_enabled ? "사용 중" : "꺼짐"}`} className="max-w-md">
        {!me.data?.totp_enabled && !setup && <Btn testId="otp-setup" onClick={() => run(async () => setSetup(await api("/auth/2fa/setup", { method: "POST" })), "인증 앱에 아래 키를 등록하세요")}>2단계 인증 설정</Btn>}
        {!me.data?.totp_enabled && setup && (
          <div className="space-y-2 text-sm">
            <p>Google Authenticator 등 인증 앱에 '키 직접 입력'으로 등록하세요.</p>
            <code data-testid="otp-secret" className="block break-all rounded bg-slate-100 p-2">{setup.secret}</code>
            <details className="text-xs"><summary>otpauth URI</summary><code className="break-all">{setup.otpauth_uri}</code></details>
            <input data-testid="otp-code" placeholder="6자리 코드" className="w-full rounded border px-2 py-1" value={code} onChange={(e) => setCode(e.target.value)} />
            <Btn testId="otp-enable" onClick={() => run(async () => { await api("/auth/2fa/enable", { method: "POST", body: { code } }); setSetup(null); setCode(""); }, "2단계 인증을 켰습니다")}>확인 후 켜기</Btn>
          </div>)}
        {me.data?.totp_enabled && (
          <div className="space-y-2 text-sm">
            <input type="password" placeholder="비밀번호" className="w-full rounded border px-2 py-1" value={pw} onChange={(e) => setPw(e.target.value)} />
            <input placeholder="OTP 코드" className="w-full rounded border px-2 py-1" value={code} onChange={(e) => setCode(e.target.value)} />
            <Btn tone="danger" onClick={() => run(async () => { await api("/auth/2fa/disable", { method: "POST", body: { password: pw, code } }); setPw(""); setCode(""); }, "2단계 인증을 껐습니다")}>2단계 인증 끄기</Btn>
          </div>)}
      </Card>
    </Page>
  );
}
