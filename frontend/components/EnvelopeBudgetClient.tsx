"use client";

import { Loader2, PencilLine, PiggyBank, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { ACTIVE_PROFILE_EVENT } from "@/lib/active-profile";
import { api, ApiError } from "@/lib/api";
import { amountToKurus, formatKurus } from "@/lib/format";
import { amountInput, isValidAmount, normalizeAmountInput } from "@/lib/money-input";
import { cn } from "@/lib/utils";
import type {
  Category,
  CategoryBudgetUpdateInput,
  EnvelopeCreateInput,
  TransactionBudgetEnvelope,
  TransactionSummary,
} from "@/lib/types";

const envelopeStatusLabels: Record<TransactionBudgetEnvelope["status"], string> = {
  safe: "Rahat",
  watch: "Dikkat",
  over: "Aşıldı",
};

function friendlyError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

function percentValue(value: string | null): number | null {
  if (value === null) return null;
  const parsed = Number(value.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function formatUsedPercent(value: string | null): string {
  const parsed = percentValue(value);
  if (parsed === null) return "Limit yok";
  return `%${new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(parsed)} kullanıldı`;
}

function envelopeHref(slug: string): string {
  return `/goals?zarf=${encodeURIComponent(slug)}`;
}

function slugFromLocation(): string | null {
  return new URL(window.location.href).searchParams.get("zarf");
}

function orderedEnvelopes(envelopes: TransactionBudgetEnvelope[]): TransactionBudgetEnvelope[] {
  return envelopes
    .map((envelope, index) => ({ envelope, index }))
    .sort((first, second) => {
      const priority = (envelope: TransactionBudgetEnvelope) => {
        if (amountToKurus(envelope.budget) <= 0) return 4;
        if (envelope.status === "over") return 0;
        if (envelope.status === "watch") return 1;
        if (envelope.is_savings_goal) return 2;
        return 3;
      };
      return priority(first.envelope) - priority(second.envelope) || first.index - second.index;
    })
    .map(({ envelope }) => envelope);
}

function statusClassName(envelope: TransactionBudgetEnvelope): string {
  if (amountToKurus(envelope.budget) <= 0) return "bg-muted text-muted-foreground";
  if (envelope.is_savings_goal) return "border border-primary/40 bg-primary/10 text-primary";
  if (envelope.status === "over") return "bg-destructive text-destructive-foreground";
  if (envelope.status === "watch") return "bg-accent text-accent-foreground";
  return "border border-border/70 bg-background text-foreground";
}

function statusLabel(envelope: TransactionBudgetEnvelope): string {
  if (amountToKurus(envelope.budget) <= 0) return "Kapalı";
  if (envelope.is_savings_goal) return "Birikim";
  return envelopeStatusLabels[envelope.status];
}

function envelopeActionText(envelope: TransactionBudgetEnvelope): string {
  if (amountToKurus(envelope.budget) <= 0) return "Zarfı aç";
  return "Limiti güncelle";
}

function baseEnvelopeName(envelope: TransactionBudgetEnvelope): string {
  return envelope.label.endsWith(" zarfı") ? envelope.label.slice(0, -6) : envelope.label;
}

function progressClassName(envelope: TransactionBudgetEnvelope): string {
  if (amountToKurus(envelope.budget) <= 0) return "bg-muted-foreground/25";
  if (envelope.is_savings_goal) return "bg-primary";
  if (envelope.status === "over") return "bg-destructive";
  if (envelope.status === "watch") return "bg-accent";
  return "bg-muted-foreground/45";
}

function progressPercent(envelope: TransactionBudgetEnvelope): number {
  const budget = amountToKurus(envelope.budget);
  const spent = amountToKurus(envelope.spent);
  return budget > 0 ? Math.min(100, Math.max(0, (spent / budget) * 100)) : 0;
}

function detailNote(envelope: TransactionBudgetEnvelope): string {
  if (amountToKurus(envelope.budget) <= 0) {
    return "Bu zarf kapalı. Yeni bir aylık limit verdiğinde tekrar takip edilir.";
  }
  if (envelope.is_savings_goal) {
    return "Bu zarf harcama uyarısı değil; ay içindeki birikim hedefini görünür tutar.";
  }
  if (envelope.status === "over") {
    return "Bu zarf aylık sınırı geçti. Yeni gider eklemeden önce son kayıtları kontrol etmek iyi olur.";
  }
  if (envelope.status === "watch") {
    return "Bu zarf sınıra yaklaştı. Ay sonuna kadar güvenli günlük tutarı referans alabilirsin.";
  }
  return "Bu zarf şu an rahat görünüyor. Kalan tutar ay sonuna kadar kullanılabilir.";
}

function EnvelopeBudgetRow({
  envelope,
  isActive,
  onSelect,
}: {
  envelope: TransactionBudgetEnvelope;
  isActive: boolean;
  onSelect: (slug: string) => void;
}) {
  const budget = amountToKurus(envelope.budget);
  const spent = amountToKurus(envelope.spent);
  const remaining = amountToKurus(envelope.remaining);
  const safeDailyAmount = amountToKurus(envelope.safe_daily_amount);
  const isClosed = budget <= 0;

  return (
    <button
      type="button"
      aria-pressed={isActive}
      onClick={() => onSelect(envelope.slug)}
      className={cn(
        "group w-full rounded-[1.35rem] border p-4 text-left transition-all duration-200 ease-quint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        isActive
          ? envelope.is_savings_goal
            ? "border-primary/65 bg-primary/10 shadow-sm"
            : "border-foreground/25 bg-background/85 shadow-sm"
          : "border-border/70 bg-background/60 hover:-translate-y-0.5 hover:border-foreground/20 hover:bg-background/85",
      )}
    >
      <div className="grid gap-4 lg:grid-cols-[minmax(11rem,0.9fr)_minmax(15rem,1.2fr)_minmax(20rem,1.4fr)] lg:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "rounded-full px-2.5 py-1 text-[0.68rem] font-black",
                statusClassName(envelope),
              )}
            >
              {statusLabel(envelope)}
            </span>
            {isActive ? (
              <span className="rounded-full border border-border/70 bg-card px-2.5 py-1 text-[0.68rem] font-black text-muted-foreground">
                Seçili
              </span>
            ) : null}
          </div>
          <p className="mt-3 truncate font-display text-2xl font-black leading-none">
            {envelope.label}
          </p>
          <p className="mt-1 truncate text-xs font-bold text-muted-foreground">
            {envelope.category_name} kategorisi
          </p>
        </div>

        <div className="space-y-2">
          <div className="h-2.5 overflow-hidden rounded-full bg-muted">
            <div
              className={cn("h-full rounded-full transition-all", progressClassName(envelope))}
              style={{ width: `${progressPercent(envelope)}%` }}
            />
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-bold text-muted-foreground">
            <span>{formatUsedPercent(envelope.used_percent)}</span>
            <span>
              {isClosed ? "Limit bekliyor" : `Ay sonuna ${envelope.days_left_in_month} gün`}
            </span>
          </div>
        </div>

        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ["Limit", formatKurus(budget), "text-foreground"],
            [
              envelope.is_savings_goal ? "Biriken" : "Harcanan",
              formatKurus(spent),
              "text-foreground",
            ],
            [
              "Kalan",
              formatKurus(remaining),
              remaining < 0 ? "text-destructive" : "text-foreground",
            ],
            [
              envelope.is_savings_goal ? "Günlük hedef" : "Güvenli günlük",
              formatKurus(safeDailyAmount),
              "text-foreground",
            ],
          ].map(([label, value, valueClassName]) => (
            <span key={label} className="rounded-[1rem] bg-card/75 p-3">
              <span className="block text-[0.7rem] font-bold text-muted-foreground">{label}</span>
              <span
                className={cn(
                  "mt-1 block font-display text-lg font-black tabular-nums",
                  valueClassName,
                )}
              >
                {value}
              </span>
            </span>
          ))}
        </div>
      </div>

      {isActive ? (
        <p className="mt-4 rounded-[1rem] border border-dashed border-border/70 bg-card/65 px-3 py-2 text-sm leading-6 text-muted-foreground">
          {detailNote(envelope)}
        </p>
      ) : null}
    </button>
  );
}

export function EnvelopeBudgetClient({ embedded = false }: { embedded?: boolean }) {
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [summary, setSummary] = useState<TransactionSummary | null>(null);
  const [budgetDrafts, setBudgetDrafts] = useState<Record<string, string>>({});
  const [newEnvelopeName, setNewEnvelopeName] = useState("");
  const [newEnvelopeBudget, setNewEnvelopeBudget] = useState("");
  const [savingSlug, setSavingSlug] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSummary = useCallback(async () => {
    setError(null);
    try {
      const nextSummary = await api<TransactionSummary>("/api/transactions/summary", {
        silent: true,
      });
      setSummary(nextSummary);
      setBudgetDrafts((current) => {
        const next = { ...current };
        for (const envelope of nextSummary.envelopes) {
          if (!(envelope.slug in next)) next[envelope.slug] = amountInput(envelope.budget);
        }
        return next;
      });
    } catch (err) {
      setError(friendlyError(err, "Zarf bütçesi yüklenemedi, biraz sonra tekrar dener misin?"));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    setSelectedSlug(slugFromLocation());
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    function handlePopState() {
      setSelectedSlug(slugFromLocation());
    }

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  useEffect(() => {
    function handleActiveProfileChange() {
      setIsLoading(true);
      void loadSummary();
    }

    window.addEventListener(ACTIVE_PROFILE_EVENT, handleActiveProfileChange);
    window.addEventListener("storage", handleActiveProfileChange);
    return () => {
      window.removeEventListener(ACTIVE_PROFILE_EVENT, handleActiveProfileChange);
      window.removeEventListener("storage", handleActiveProfileChange);
    };
  }, [loadSummary]);

  const envelopes = useMemo(() => orderedEnvelopes(summary?.envelopes ?? []), [summary]);
  const selectedEnvelope =
    (selectedSlug ? envelopes.find((envelope) => envelope.slug === selectedSlug) : null) ??
    envelopes[0] ??
    null;
  const totalBudget = amountToKurus(summary?.budgeted_month ?? "0");
  const totalRemaining = amountToKurus(summary?.remaining_budget ?? "0");
  const activeEnvelopeCount = envelopes.filter(
    (envelope) => amountToKurus(envelope.budget) > 0,
  ).length;
  const closedEnvelopeCount = Math.max(0, envelopes.length - activeEnvelopeCount);

  function selectEnvelope(slug: string) {
    setSelectedSlug(slug);
    window.history.pushState(null, "", envelopeHref(slug));
  }

  async function handleCreateEnvelopeBudget() {
    const name = newEnvelopeName.trim();
    const normalized = normalizeAmountInput(newEnvelopeBudget);
    if (name.length < 2) {
      setError("Zarf adını en az 2 karakter yazar mısın?");
      return;
    }
    if (!isValidAmount(normalized) || amountToKurus(normalized) <= 0) {
      setError("Yeni zarf limitini 1250,50 biçiminde ve 0'dan büyük girer misin?");
      return;
    }

    setIsCreating(true);
    setError(null);
    try {
      const category = await api<Category>("/api/categories/envelopes", {
        method: "POST",
        body: { name, budget_monthly: normalized } satisfies EnvelopeCreateInput,
      });
      const nextSummary = await api<TransactionSummary>("/api/transactions/summary", {
        silent: true,
      });
      const existingEnvelope = nextSummary.envelopes.find(
        (envelope) =>
          envelope.category_name.toLocaleLowerCase("tr-TR") ===
          category.name.toLocaleLowerCase("tr-TR"),
      );
      setSummary(nextSummary);
      setNewEnvelopeName("");
      setNewEnvelopeBudget("");
      if (existingEnvelope) {
        setSelectedSlug(existingEnvelope.slug);
        setBudgetDrafts((current) => ({
          ...current,
          [existingEnvelope.slug]: amountInput(existingEnvelope.budget),
        }));
        window.history.pushState(null, "", envelopeHref(existingEnvelope.slug));
      }
    } catch (err) {
      setError(friendlyError(err, "Zarf eklenemedi, tekrar dener misin?"));
    } finally {
      setIsCreating(false);
    }
  }

  async function handleSaveEnvelopeBudget(envelope: TransactionBudgetEnvelope) {
    const normalized = normalizeAmountInput(budgetDrafts[envelope.slug] ?? "");
    if (!isValidAmount(normalized)) {
      setError("Zarf limitini 1250,50 biçiminde girer misin?");
      return;
    }

    setSavingSlug(envelope.slug);
    setError(null);
    try {
      await api<Category>(`/api/categories/envelopes/${envelope.slug}`, {
        method: "PATCH",
        body: { budget_monthly: normalized } satisfies CategoryBudgetUpdateInput,
      });
      const nextSummary = await api<TransactionSummary>("/api/transactions/summary", {
        silent: true,
      });
      setSummary(nextSummary);
      setBudgetDrafts((current) => ({ ...current, [envelope.slug]: amountInput(normalized) }));
      setSelectedSlug(envelope.slug);
      window.history.pushState(null, "", envelopeHref(envelope.slug));
    } catch (err) {
      setError(friendlyError(err, "Zarf limiti güncellenemedi, tekrar dener misin?"));
    } finally {
      setSavingSlug(null);
    }
  }

  async function handleDeleteEnvelopeBudget(envelope: TransactionBudgetEnvelope) {
    const confirmed = window.confirm(
      `${envelope.label} silinsin mi? Bu işlem zarf limitini 0,00 ₺ yapar; sonra yeniden limit verebilirsin.`,
    );
    if (!confirmed) return;

    setSavingSlug(envelope.slug);
    setError(null);
    try {
      await api<void>(`/api/categories/envelopes/${envelope.slug}`, { method: "DELETE" });
      const nextSummary = await api<TransactionSummary>("/api/transactions/summary", {
        silent: true,
      });
      setSummary(nextSummary);
      setBudgetDrafts((current) => ({ ...current, [envelope.slug]: "0,00" }));
      setSelectedSlug(envelope.slug);
    } catch (err) {
      setError(friendlyError(err, "Zarf silinemedi, tekrar dener misin?"));
    } finally {
      setSavingSlug(null);
    }
  }

  function handleBudgetDraftChange(slug: string, value: string) {
    setBudgetDrafts((current) => ({ ...current, [slug]: value }));
  }

  return (
    <section
      id="zarflar"
      className={cn(
        "scroll-mt-24 rounded-[1.8rem] border border-border/80 bg-card/80 p-4 shadow-sm sm:p-5",
        embedded ? "" : "page-enter",
      )}
    >
      <div className="receipt-tape hard-shadow relative overflow-hidden rounded-[2rem] border border-border/80 bg-card p-5 sm:p-6">
        <div className="relative z-10 space-y-5">
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem] xl:items-start">
            <div>
              <span className="stamp-label bg-primary/10 text-primary">Yeni zarf ekle</span>
              <h2 className="mt-4 font-display text-[2.35rem] font-black leading-none sm:text-5xl">
                Harcama zarfı oluştur
              </h2>
              <p className="mt-3 max-w-[68ch] text-sm leading-6 text-muted-foreground sm:text-base">
                Zarf adını ve aylık limitini yaz. Hazır zarflardan birinin adını kullanırsan o
                zarfın limiti açılır; farklı ad yazarsan özel zarf oluşturulur.
              </p>
            </div>

            <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-1">
              <div className="rounded-[1.2rem] bg-background/70 p-3">
                <p className="text-xs font-bold text-muted-foreground">Toplam limit</p>
                <p className="mt-1 font-display text-2xl font-black tabular-nums">
                  {formatKurus(totalBudget)}
                </p>
              </div>
              <div className="rounded-[1.2rem] bg-background/70 p-3">
                <p className="text-xs font-bold text-muted-foreground">Kalan</p>
                <p className="mt-1 font-display text-2xl font-black tabular-nums">
                  {formatKurus(totalRemaining)}
                </p>
              </div>
              <div className="rounded-[1.2rem] bg-background/70 p-3">
                <p className="text-xs font-bold text-muted-foreground">Açık / kapalı</p>
                <p className="mt-1 font-display text-2xl font-black tabular-nums">
                  {activeEnvelopeCount}/{closedEnvelopeCount}
                </p>
              </div>
            </div>
          </div>

          <form
            className="rounded-[1.5rem] border border-primary/30 bg-primary/10 p-4 shadow-sm"
            onSubmit={(event) => {
              event.preventDefault();
              void handleCreateEnvelopeBudget();
            }}
          >
            <div className="grid gap-3 lg:grid-cols-[minmax(13rem,0.8fr)_minmax(10rem,0.65fr)_auto] lg:items-end">
              <label className="grid gap-1.5">
                <span className="text-xs font-black uppercase tracking-[0.16em] text-primary">
                  Zarf adı
                </span>
                <input
                  className="h-12 rounded-xl border border-primary/30 bg-background px-3 text-sm font-bold"
                  value={newEnvelopeName}
                  onChange={(event) => setNewEnvelopeName(event.target.value)}
                  placeholder="Örn. Evcil hayvan"
                  list="envelope-name-suggestions"
                  disabled={isCreating}
                />
                <datalist id="envelope-name-suggestions">
                  {envelopes.map((envelope) => (
                    <option key={envelope.slug} value={baseEnvelopeName(envelope)} />
                  ))}
                </datalist>
              </label>

              <label className="grid gap-1.5">
                <span className="text-xs font-black uppercase tracking-[0.16em] text-primary">
                  Aylık limit
                </span>
                <input
                  className="h-12 rounded-xl border border-primary/30 bg-background px-3 text-sm font-bold tabular-nums"
                  inputMode="decimal"
                  value={newEnvelopeBudget}
                  disabled={isCreating}
                  onChange={(event) => setNewEnvelopeBudget(event.target.value)}
                  placeholder="2500,00"
                />
              </label>

              <Button type="submit" className="min-h-12 sm:w-fit" disabled={isCreating}>
                {isCreating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <PiggyBank className="h-4 w-4" />
                )}
                Zarf ekle
              </Button>
            </div>
            <p className="mt-3 text-xs font-medium leading-5 text-primary/90">
              Örnekler: Market, Fatura, Okul, Ulaşım, Harçlık, Birikim veya kendi zarf adın.
            </p>
          </form>

          <form
            className="bg-background/72 rounded-[1.5rem] border border-dashed border-border/80 p-4"
            onSubmit={(event) => {
              event.preventDefault();
              if (selectedEnvelope) void handleSaveEnvelopeBudget(selectedEnvelope);
            }}
          >
            <div className="grid gap-3 lg:grid-cols-[minmax(13rem,0.8fr)_minmax(10rem,0.65fr)_auto] lg:items-end">
              <label className="grid gap-1.5">
                <span className="text-xs font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  Mevcut zarfı düzenle
                </span>
                <select
                  className="h-11 rounded-xl border border-input bg-background px-3 text-sm font-bold"
                  value={selectedEnvelope?.slug ?? ""}
                  disabled={isLoading || envelopes.length === 0}
                  onChange={(event) => selectEnvelope(event.target.value)}
                >
                  {envelopes.map((envelope) => (
                    <option key={envelope.slug} value={envelope.slug}>
                      {envelope.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="grid gap-1.5">
                <span className="text-xs font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  Yeni limit
                </span>
                <input
                  className="h-11 rounded-xl border border-input bg-background px-3 text-sm font-bold tabular-nums"
                  inputMode="decimal"
                  value={
                    selectedEnvelope
                      ? (budgetDrafts[selectedEnvelope.slug] ??
                        amountInput(selectedEnvelope.budget))
                      : ""
                  }
                  disabled={!selectedEnvelope || savingSlug === selectedEnvelope.slug}
                  onChange={(event) => {
                    if (!selectedEnvelope) return;
                    handleBudgetDraftChange(selectedEnvelope.slug, event.target.value);
                  }}
                  placeholder="2500,00"
                />
              </label>

              <div className="grid gap-2 sm:flex lg:justify-end">
                <Button
                  type="submit"
                  className="min-h-11 sm:w-fit"
                  disabled={!selectedEnvelope || savingSlug === selectedEnvelope.slug}
                >
                  {selectedEnvelope && savingSlug === selectedEnvelope.slug ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <PencilLine className="h-4 w-4" />
                  )}
                  {selectedEnvelope ? envelopeActionText(selectedEnvelope) : "Zarfı kaydet"}
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  className="min-h-11 text-destructive hover:text-destructive sm:w-fit"
                  disabled={
                    !selectedEnvelope ||
                    amountToKurus(selectedEnvelope.budget) <= 0 ||
                    savingSlug === selectedEnvelope.slug
                  }
                  onClick={() => {
                    if (!selectedEnvelope) return;
                    void handleDeleteEnvelopeBudget(selectedEnvelope);
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                  Zarfı sil
                </Button>
              </div>
            </div>
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              Silmek gerçek kategoriyi kaldırmaz; seçili profil için limiti 0,00 ₺ yapar. Yeniden
              limit verince zarf tekrar açılır.
            </p>
          </form>
        </div>
      </div>

      {error ? (
        <p className="mt-4 rounded-2xl border border-destructive/35 bg-destructive/10 px-4 py-3 text-sm font-semibold">
          {error}
        </p>
      ) : null}

      {isLoading ? (
        <div className="mt-4 rounded-[1.25rem] border border-border/70 bg-background/70 p-4">
          <div className="flex items-center gap-2 text-sm font-bold text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Zarflar yükleniyor.
          </div>
        </div>
      ) : envelopes.length === 0 ? (
        <div className="mt-4 rounded-[1.25rem] border border-border/70 bg-background/70 p-5">
          <PiggyBank className="h-6 w-6 text-primary" />
          <p className="mt-3 font-display text-xl font-black">Henüz zarf görünmüyor.</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Kategori bütçeleri oluşunca zarf listesi burada görünecek.
          </p>
        </div>
      ) : (
        <div className="mt-4 grid gap-3">
          <div className="flex flex-wrap items-end justify-between gap-3 px-1">
            <div>
              <p className="eyebrow">Mevcut zarflar</p>
              <h3 className="mt-1 font-display text-2xl font-black leading-none">Takip listesi</h3>
            </div>
            <p className="max-w-md text-sm leading-6 text-muted-foreground">
              Limitini değiştirmek için zarfı seç; yeni zarf eklemek için üstteki yeşil formu
              kullan.
            </p>
          </div>
          {envelopes.map((envelope) => (
            <EnvelopeBudgetRow
              key={envelope.slug}
              envelope={envelope}
              isActive={selectedEnvelope?.slug === envelope.slug}
              onSelect={selectEnvelope}
            />
          ))}
        </div>
      )}
    </section>
  );
}
