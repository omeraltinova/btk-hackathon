/**
 * Typed fetch helper for the FastAPI backend.
 *
 * Why a thin wrapper (and not a heavyweight client like axios or tRPC):
 * - Reads `NEXT_PUBLIC_API_URL` once.
 * - Attaches the FastAPI JWT carried by the NextAuth session.
 * - Surfaces Turkish error messages via `sonner` toasts so every router gets
 *   a consistent UX without repeating boilerplate.
 *
 * Usage (from a client component):
 *   const data = await api<Transaction[]>("/api/transactions");
 *   const created = await api<Transaction>("/api/transactions", {
 *     method: "POST",
 *     body: { amount: "1250.50", type: "expense" },
 *   });
 *   const receipt = await api<ReceiptCandidate>("/api/receipts/upload", {
 *     method: "POST",
 *     body: formData,
 *   });
 */

import { toast } from "sonner";

import { getBackendToken } from "@/lib/active-profile";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  /** JSON-serialisable body or FormData. JSON bodies are stringified for you. */
  body?: unknown;
  /** Extra headers; merged with defaults. */
  headers?: Record<string, string>;
  /** AbortSignal for in-flight cancellation (e.g. on route change). */
  signal?: AbortSignal;
  /** When true, skip toasts on error and rethrow only — for components that
   *  want to render their own error UI. Defaults to false. */
  silent?: boolean;
  /** Use the active child profile token when one is selected. Defaults to true. */
  useActiveProfile?: boolean;
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
  const {
    method = "GET",
    body,
    headers = {},
    signal,
    silent = false,
    useActiveProfile = true,
  } = options;

  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`;
  const isFormData = typeof FormData !== "undefined" && body instanceof FormData;

  const finalHeaders: Record<string, string> = {
    Accept: "application/json",
    ...headers,
  };
  if (body !== undefined && !isFormData) finalHeaders["Content-Type"] = "application/json";

  const token = await getBackendToken(useActiveProfile);
  if (token) finalHeaders.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: finalHeaders,
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
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

/**
 * Trigger a browser download for a binary endpoint (e.g. ZIP / CSV exports).
 *
 * Mirrors `api()` for auth and active-profile handling, but pulls the response
 * as a Blob and clicks a synthetic anchor so the browser handles the save
 * dialog. Errors still travel as `ApiError` so callers can surface inline UX.
 */
export async function apiDownload(path: string, filename: string): Promise<void> {
  const url = path.startsWith("http") ? path : `${BASE_URL}${path}`;
  const headers: Record<string, string> = { Accept: "application/octet-stream" };
  const token = await getBackendToken(true);
  if (token) headers.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(url, { method: "GET", headers, credentials: "include" });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    const message = describeError(0, undefined);
    throw new ApiError(0, message);
  }

  if (!response.ok) {
    let detail: string | undefined;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      // ignore: non-JSON error bodies fall back to describeError defaults.
    }
    throw new ApiError(response.status, describeError(response.status, detail));
  }

  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}
