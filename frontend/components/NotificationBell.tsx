"use client";

import { Bell, CheckCheck, ExternalLink, Loader2, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import { ACTIVE_PROFILE_EVENT } from "@/lib/active-profile";
import { api } from "@/lib/api";
import type { ProactiveInsight } from "@/lib/types";
import { cn } from "@/lib/utils";

type NotificationBellProps = {
  collapsed?: boolean;
};

const severityLabels: Record<ProactiveInsight["severity"], string> = {
  info: "Bilgi",
  warning: "Dikkat",
  critical: "Öncelikli",
};

const SEEN_STORAGE_KEY = "cuzdan-kocu.bell-seen";
const UNDO_TIMEOUT_MS = 5000;

function readSeenIds(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(SEEN_STORAGE_KEY);
    if (!raw) return new Set();
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? new Set(parsed.filter((value): value is string => typeof value === "string"))
      : new Set();
  } catch {
    return new Set();
  }
}

function writeSeenIds(ids: Set<string>): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(SEEN_STORAGE_KEY, JSON.stringify(Array.from(ids)));
  } catch {
    // localStorage is a best-effort store; surface no UI on failure.
  }
}

function insightHref(insight: ProactiveInsight): string {
  if (insight.insight_type === "receipt_activity") return "/transactions";
  if (insight.insight_type === "upcoming_recurring") return "/transactions";
  if (insight.insight_type === "savings_opportunity") return "/goals";
  if (insight.insight_type.includes("goal")) return "/goals";
  return "/dashboard";
}

function formatInsightDate(value: string): string {
  return new Intl.DateTimeFormat("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Istanbul",
  }).format(new Date(value));
}

export function NotificationBell({ collapsed = false }: NotificationBellProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [insights, setInsights] = useState<ProactiveInsight[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [seenIds, setSeenIds] = useState<Set<string>>(() => new Set());
  const panelRef = useRef<HTMLDivElement | null>(null);
  const pendingDismissalsRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  async function loadInsights() {
    setIsLoading(true);
    setError(null);
    try {
      const rows = await api<ProactiveInsight[]>("/api/insights", { silent: true });
      setInsights(rows.filter((insight) => !insight.is_dismissed));
    } catch {
      setError("Bildirimler yüklenemedi.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    setSeenIds(readSeenIds());
    void loadInsights();
    function handleActiveProfileChange() {
      void loadInsights();
    }
    window.addEventListener(ACTIVE_PROFILE_EVENT, handleActiveProfileChange);
    return () => window.removeEventListener(ACTIVE_PROFILE_EVENT, handleActiveProfileChange);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    function handlePointerDown(event: MouseEvent) {
      if (!panelRef.current?.contains(event.target as Node)) setIsOpen(false);
    }
    window.addEventListener("mousedown", handlePointerDown);
    return () => window.removeEventListener("mousedown", handlePointerDown);
  }, [isOpen]);

  // After the panel is open for a moment, mark currently shown insights as seen.
  useEffect(() => {
    if (!isOpen || insights.length === 0) return;
    const timer = window.setTimeout(() => {
      setSeenIds((current) => {
        const next = new Set(current);
        for (const insight of insights) next.add(insight.id);
        writeSeenIds(next);
        return next;
      });
    }, 1200);
    return () => window.clearTimeout(timer);
  }, [isOpen, insights]);

  // Cancel any pending dismissal timers if the component unmounts.
  useEffect(() => {
    const timers = pendingDismissalsRef.current;
    return () => {
      for (const handle of timers.values()) clearTimeout(handle);
      timers.clear();
    };
  }, []);

  function markAllAsRead() {
    setSeenIds((current) => {
      const next = new Set(current);
      for (const insight of insights) next.add(insight.id);
      writeSeenIds(next);
      return next;
    });
  }

  function dismissInsight(insightId: string) {
    const target = insights.find((insight) => insight.id === insightId);
    if (target === undefined) return;
    if (pendingDismissalsRef.current.has(insightId)) return;

    // Optimistically hide the row.
    setInsights((current) => current.filter((insight) => insight.id !== insightId));
    setError(null);

    const timer = setTimeout(() => {
      pendingDismissalsRef.current.delete(insightId);
      void (async () => {
        try {
          await api<ProactiveInsight>(`/api/insights/${insightId}/dismiss`, {
            method: "PATCH",
            silent: true,
          });
        } catch {
          // Restore the insight if the server rejects so the user sees it again.
          setInsights((current) =>
            current.some((insight) => insight.id === insightId) ? current : [target, ...current],
          );
          toast.error("Bildirim kapatılamadı, tekrar dener misin?");
        }
      })();
    }, UNDO_TIMEOUT_MS);
    pendingDismissalsRef.current.set(insightId, timer);

    toast("Bildirim kapatıldı.", {
      action: {
        label: "Geri al",
        onClick: () => {
          const pending = pendingDismissalsRef.current.get(insightId);
          if (pending !== undefined) {
            clearTimeout(pending);
            pendingDismissalsRef.current.delete(insightId);
          }
          setInsights((current) =>
            current.some((insight) => insight.id === insightId) ? current : [target, ...current],
          );
        },
      },
      duration: UNDO_TIMEOUT_MS,
    });
  }

  const unseenCount = useMemo(
    () => insights.filter((insight) => !seenIds.has(insight.id)).length,
    [insights, seenIds],
  );
  const count = unseenCount;

  return (
    <div ref={panelRef} className="relative">
      <button
        type="button"
        aria-label={`Bildirimler${count > 0 ? `, ${count} yeni` : ""}`}
        title="Bildirimler"
        onClick={() => setIsOpen((current) => !current)}
        className={cn(
          "relative inline-flex h-10 items-center justify-center gap-2 rounded-[1rem] border border-border/70 bg-background/70 px-3 text-sm font-bold text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
          collapsed ? "lg:w-10 lg:px-0" : "",
        )}
      >
        <Bell className="h-4 w-4" />
        <span className={cn(collapsed && "lg:hidden")}>Bildirim</span>
        {count > 0 ? (
          <span className="absolute -right-1 -top-1 grid min-h-5 min-w-5 place-items-center rounded-full bg-primary px-1 text-[0.68rem] font-black text-primary-foreground">
            {count > 9 ? "9+" : count}
          </span>
        ) : null}
      </button>

      {isOpen ? (
        <div className="absolute right-0 top-12 z-50 w-[min(22rem,calc(100vw-2rem))] rounded-[1.4rem] border border-border/80 bg-card p-3 shadow-xl lg:left-0 lg:right-auto">
          <div className="flex items-start justify-between gap-3 border-b border-border/70 pb-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-muted-foreground">
                Bildirim merkezi
              </p>
              <p className="mt-1 font-display text-xl font-black">Koç notları</p>
            </div>
            <div className="flex items-center gap-1">
              {isLoading ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : null}
              {unseenCount > 0 ? (
                <button
                  type="button"
                  onClick={markAllAsRead}
                  className="inline-flex items-center gap-1 rounded-full bg-muted/45 px-2 py-1 text-[0.68rem] font-bold text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                  title="Tümünü okundu işaretle"
                  aria-label="Tümünü okundu işaretle"
                >
                  <CheckCheck className="h-3 w-3" />
                  Tümü okundu
                </button>
              ) : null}
            </div>
          </div>

          {error ? <p className="mt-3 text-sm font-semibold text-destructive">{error}</p> : null}

          <div className="mt-3 max-h-[28rem] space-y-2 overflow-y-auto pr-1">
            {insights.length === 0 && !isLoading ? (
              <div className="rounded-2xl border border-dashed border-border/80 bg-muted/35 p-4 text-sm text-muted-foreground">
                Açık bildirim yok. Koç yeni bir içgörü bulduğunda burada görünür.
              </div>
            ) : null}

            {insights.slice(0, 6).map((insight) => {
              const isUnseen = !seenIds.has(insight.id);
              return (
                <article
                  key={insight.id}
                  className={cn(
                    "rounded-2xl border p-3 transition-colors",
                    isUnseen ? "border-primary/45 bg-primary/5" : "border-border/70 bg-muted/35",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <span className="rounded-full bg-background/80 px-2 py-0.5 text-[0.68rem] font-black text-muted-foreground">
                        {severityLabels[insight.severity]} · {formatInsightDate(insight.created_at)}
                      </span>
                      <h3 className="mt-2 line-clamp-2 font-display text-base font-black">
                        {insight.title}
                      </h3>
                    </div>
                    <button
                      type="button"
                      aria-label="Bildirimi kapat"
                      onClick={() => dismissInsight(insight.id)}
                      className="rounded-full p-1 text-muted-foreground transition-colors hover:bg-background hover:text-foreground"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <p className="mt-2 line-clamp-3 text-sm leading-5 text-muted-foreground">
                    {insight.content}
                  </p>
                  <Link
                    href={insightHref(insight)}
                    onClick={() => setIsOpen(false)}
                    className="mt-3 inline-flex items-center gap-1 text-xs font-black text-primary hover:underline"
                  >
                    {insight.action_label ?? "Detaya bak"}
                    <ExternalLink className="h-3.5 w-3.5" />
                  </Link>
                </article>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}
