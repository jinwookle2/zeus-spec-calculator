"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function Login() {
  const [email, setEmail] = useState("admin@example.com");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [otp, setOtp] = useState("");
  const [needOtp, setNeedOtp] = useState(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    try {
      const r = await api<{ access_token: string; role: string; email: string }>("/auth/login", { method: "POST", body: { email, password, otp: otp || undefined } });
      localStorage.setItem("token", r.access_token);
      localStorage.setItem("role", r.role);
      localStorage.setItem("email", r.email);
      window.location.href = "/";
    } catch (e) {
      const m = (e as Error).message;
      if (m === "OTP_REQUIRED") { setNeedOtp(true); setErr("인증 앱의 6자리 코드를 입력하세요"); }
      else setErr(m);
    }
  }
  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-lg bg-white p-6 shadow">
        <h1 className="text-lg font-bold">스마트스토어 자동화 관리자</h1>
        <label className="block text-sm">이메일
          <input name="email" className="mt-1 w-full rounded border px-3 py-2" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="block text-sm">비밀번호
          <input name="password" type="password" className="mt-1 w-full rounded border px-3 py-2" value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {needOtp && (
          <label className="block text-sm">OTP 코드
            <input name="otp" inputMode="numeric" autoComplete="one-time-code" className="mt-1 w-full rounded border px-3 py-2" value={otp} onChange={(e) => setOtp(e.target.value)} />
          </label>)}
        {err && <p className="text-sm text-red-600">{err}</p>}
        <button type="submit" className="w-full rounded bg-slate-900 py-2 text-white">로그인</button>
      </form>
    </div>
  );
}
