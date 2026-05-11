/**
 * Typed fetch helper for the FastAPI backend.
 *
 * Why a thin wrapper (and not a heavyweight client like axios or tRPC):
 * - Reads `NEXT_PUBLIC_API_URL` once.
 * - Attaches the JWT from localStorage (Day 2 will plug in NextAuth session).
 * - Surfaces Turkish error messages via `sonner` toasts so every router gets
 *   a consistent UX without repeating boilerplate.
 *
 * Usage (from a client component):
 *   const data = await api<Transaction[]>("/api/transactions");
 *   const created = await api<Transaction>("/api/transactions", {
 *     method: "POST",
 *     body: { amount: "1250.50", type: "expense" },
 *   });
 */

import { toast } from "sonner";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_STORAGE_KEY = "cuzdan_kocu_token";

export type ApiOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** JSON-serialisable body. We `JSON.stringify` it for you. */
  body?: unknown;
  /** Extra headers; merged with defaults. */
  headers?: Record<string, string>;
  /** AbortSignal for in-flight cancellation (e.g. on route change). */
  signal?: AbortSignal;
  /** When true, skip toasts on error and rethrow only — for components that
   *  want to render their own error UI. Defaults to false. */
  silent?: boolean;
};

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setToken(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearToken(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_STORAGE_KEY);
}

/**
 * Map a backend error into a Turkish, user-facing message.
 * The backend already returns Turkish details for known errors; this is a
 * fallback for transport-level failures (network, 5xx without body).
 */
function describeError(status: number, raw: string | undefined): string {
  if (raw && raw.trim().length > 0) return raw;
  if (status === 0) return "Sunucuya ulaşılamadı, internet bağlantını kontrol et.";
  if (status === 401) return "Oturum süresi dolmuş olabilir, tekrar giriş yap.";
  if (status === 403) return "Bu işlem için yetkin yok.";
  if (status === 404) return "Aradığın şey bulunamadı.";
  if (status >= 500) return "Sunucuda bir sorun çıktı, biraz sonra tekrar dener misin?";
  return "Bir sorun çıktı, tekrar dener misin?";
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { method = "GET", body, headers = {}, signal, silent = false } = options;

  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`;

  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };
  if (body !== undefined) finalHeaders["Content-Type"] = "application/json";

  const token = getToken();
  if (token) finalHeaders.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: finalHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      credentials: "include",
    });
  } catch (err) {
    // Network / abort failure — no Response object.
    if ((err as Error).name === "AbortError") throw err;
    const message = describeError(0, undefined);
    if (!silent) toast.error(message);
    throw new ApiError(0, message);
  }

  // 204 No Content → return undefined cast to T.
  if (response.status === 204) return undefined as T;

  let payload: unknown = null;
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const detail =
      typeof payload === "object" && payload !== null && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : undefined;
    const message = describeError(response.status, detail);
    if (!silent) toast.error(message);
    throw new ApiError(response.status, message);
  }

  return payload as T;
}
