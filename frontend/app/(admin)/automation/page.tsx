"use client";

import { useEffect, useState } from "react";
import { Btn, Card, Msg, Page, useApi } from "@/components/ui";
import { api } from "@/lib/api";

const FIELDS: [string, string, "bool" | "num" | "json"][] = [
  ["auto_listing_enabled", "상품 자동 등록 (검증·허용된 공급사만)", "bool"],
  ["auto_purchase_enabled", "공급사 자동 발주 (검증·허용된 공급사 + 발주 API)", "bool"],
  ["listing_interval_minutes", "상품 등록 주기(분)", "num"],
  ["sourcing_interval_minutes", "상품 수집 주기(분)", "num"],
  ["order_poll_interval_minutes", "주문 수집 주기(분)", "num"],
  ["daily_listing_limit", "일일 등록 한도(개)", "num"],
  ["target_margin_rate", "목표 마진율 (0.25 = 25%)", "num"],
  ["min_profit_krw", "최소 이익금(원)", "num"],
  ["platform_fee_rates", "플랫폼 수수료율 {이름: 비율}", "json"],
  ["ad_cost_rate", "광고비 배분율", "num"],
  ["ad_cost_per_order", "주문당 광고비(원)", "num"],
  ["other_variable_cost", "주문당 기타 변동비(원)", "num"],
  ["customer_shipping_fee", "고객 부담 배송비(원)", "num"],
  ["price_rounding_unit", "판매가 올림 단위(원)", "num"],
  ["max_supply_price_increase_rate", "주문 시 공급가 상승 허용치", "num"],
  ["daily_purchase_amount_limit", "일일 발주 금액 한도(원)", "num"],
  ["max_purchase_retries", "발주 최대 재시도", "num"],
  ["banned_keywords", "판매 금지 키워드", "json"],
  ["restricted_claims", "금지 표현(효능·과장)", "json"],
  ["origin_area_codes", "원산지 → 네이버 원산지코드", "json"],
  ["carrier_code_map", "택배사 코드 매핑 덮어쓰기", "json"],
];

export default function Automation() {
  const { data, reload } = useApi("/settings");
  const [form, setForm] = useState<Record<string, string | boolean>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!data) return;
    const f: Record<string, string | boolean> = {};
    for (const [k, , t] of FIELDS) f[k] = t === "bool" ? Boolean(data[k]) : t === "json" ? JSON.stringify(data[k]) : String(data[k]);
    setForm(f);
  }, [data]);
  async function save() {
    try {
      const body: Record<string, unknown> = {};
      for (const [k, , t] of FIELDS) {
        const v = form[k];
        const parsed = t === "bool" ? v : t === "json" ? JSON.parse(String(v)) : Number(v);
        if (JSON.stringify(parsed) !== JSON.stringify(data[k])) body[k] = parsed;
      }
      await api("/settings", { method: "PUT", body });
      setMsg(`저장됨: ${Object.keys(body).join(", ") || "변경 없음"}`); setErr(null); reload();
    } catch (e) { setErr((e as Error).message); setMsg(null); }
  }
  return (
    <Page title="자동화 설정" desc="변경 내역은 감사 로그에 기록됩니다 (admin 권한)." actions={<Btn testId="save-settings" onClick={save}>저장</Btn>}>
      <Msg text={msg} /><Msg text={err} tone="error" />
      <Card>
        <div className="grid gap-3 md:grid-cols-2">
          {FIELDS.map(([k, label, t]) => (
            <label key={k} className="block text-sm">
              <span className="text-slate-600">{label}</span>
              {t === "bool" ? (
                <input data-testid={`f-${k}`} type="checkbox" className="ml-2" checked={Boolean(form[k])} onChange={(e) => setForm({ ...form, [k]: e.target.checked })} />
              ) : t === "json" ? (
                <textarea data-testid={`f-${k}`} className="mt-1 w-full rounded border px-2 py-1 font-mono text-xs" rows={2} value={String(form[k] ?? "")} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              ) : (
                <input data-testid={`f-${k}`} className="mt-1 w-full rounded border px-2 py-1" value={String(form[k] ?? "")} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              )}
            </label>
          ))}
        </div>
      </Card>
      <p className="text-xs text-slate-500">공급사별 자동 발주/자동 등록 허용은 '공급사 관리'에서 설정합니다. 실제 공개 등록·실제 결제·개인정보 전송은 서버 환경변수 안전 스위치로만 켤 수 있습니다.</p>
    </Page>
  );
}
