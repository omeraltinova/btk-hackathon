"use client";

import { ArrowLeft, BrainCircuit, Loader2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ACTIVE_PROFILE_EVENT } from "@/lib/active-profile";
import { api, ApiError } from "@/lib/api";
import { formatDateTR } from "@/lib/format";
import type { MemoryEntry } from "@/lib/types";

function friendlyError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

function formatJson(value: Record<string, unknown>): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "[okunamadı]";
  }
}

export function MemoryViewer() {
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const rows = await api<MemoryEntry[]>("/api/memory", { silent: true });
      setEntries(rows);
    } catch (err) {
      setError(friendlyError(err, "Hafıza kayıtları yüklenemedi."));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    function reload() {
      setIsLoading(true);
      void load();
    }
    window.addEventListener(ACTIVE_PROFILE_EVENT, reload);
    return () => window.removeEventListener(ACTIVE_PROFILE_EVENT, reload);
  }, [load]);

  async function handleDelete(key: string) {
    setDeletingKey(key);
    setError(null);
    try {
      await api<void>(`/api/memory/${encodeURIComponent(key)}`, {
        method: "DELETE",
        silent: true,
      });
      setEntries((current) => current.filter((entry) => entry.key !== key));
      toast.success("Hafıza kaydı silindi.");
    } catch (err) {
      setError(friendlyError(err, "Hafıza kaydı silinemedi."));
    } finally {
      setDeletingKey(null);
    }
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Koç hafızası</p>
          <h1 className="mt-2 font-display text-3xl font-black tracking-[-0.04em] sm:text-4xl">
            Koç senin için neleri hatırlıyor?
          </h1>
          <p className="mt-2 max-w-[60ch] text-sm text-muted-foreground">
            Cüzdan Koçu, senin onayınla bazı bilgileri kalıcı olarak saklayabilir — örneğin bir
            tasarruf hedefi veya tercih ettiğin kategori. Aşağıdaki listede aktif profilin tüm
            kayıtları var; istediğini silebilirsin.
          </p>
        </div>
        <Button asChild variant="outline">
          <Link href="/account">
            <ArrowLeft className="h-4 w-4" />
            Hesap ayarları
          </Link>
        </Button>
      </header>

      {error ? (
        <p className="bg-destructive/14 rounded-2xl border border-destructive/35 px-4 py-3 text-sm font-semibold text-foreground shadow-sm">
          {error}
        </p>
      ) : null}

      {isLoading ? (
        <div className="receipt-tape flex items-center gap-2 px-4 py-4 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Hafıza yükleniyor...
        </div>
      ) : entries.length === 0 ? (
        <div className="receipt-tape px-5 py-10 text-center">
          <BrainCircuit className="mx-auto h-7 w-7 text-primary" />
          <h2 className="mt-3 font-display text-2xl font-black">Henüz kayıt yok</h2>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Koçla bir hedef ya da tercih paylaştığında burada görünür. Veriler yalnızca senin
            profiline aittir; aile içinde paylaşılmaz.
          </p>
        </div>
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {entries.map((entry) => (
            <li key={entry.key} className="ledger-sheet space-y-3 p-5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="eyebrow">Anahtar</p>
                  <p className="break-words font-display text-lg font-black">{entry.key}</p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  disabled={deletingKey === entry.key}
                  onClick={() => void handleDelete(entry.key)}
                >
                  {deletingKey === entry.key ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                  Sil
                </Button>
              </div>
              <pre className="overflow-x-auto rounded-2xl bg-background/70 p-3 text-xs leading-5">
                <code>{formatJson(entry.value)}</code>
              </pre>
              <p className="text-xs text-muted-foreground">
                Son güncelleme: {formatDateTR(entry.updated_at)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
