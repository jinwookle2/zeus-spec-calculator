"use client";

export type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any

export function getToken(): string | null {
  try {
    return localStorage.getItem("token");
  } catch {
    return null;
  }
}

export function getRole(): string {
  try {
    return localStorage.getItem("role") || "viewer";
  } catch {
    return "viewer";
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T = Json>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`/api${path}`, {
    method: opts.method || "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    cache: "no-store",
  });
  if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/login")) {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data?.detail;
    throw new ApiError(res.status, typeof detail === "string" ? detail : JSON.stringify(detail ?? data));
  }
  return data as T;
}

export const won = (v: string | number | null | undefined) =>
  v === null || v === undefined || v === "" ? "-" : `${Math.round(Number(v)).toLocaleString("ko-KR")}원`;

export const pct = (v: string | number | null | undefined) =>
  v === null || v === undefined ? "-" : `${(Number(v) * 100).toFixed(1)}%`;

export const dt = (v: string | null | undefined) => (v ? new Date(v).toLocaleString("ko-KR") : "-");
