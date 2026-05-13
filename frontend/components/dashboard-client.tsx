"use client";

import {
  ArrowRight,
  ArrowDownRight,
  ArrowUpRight,
  CalendarDays,
  Loader2,
  Plus,
  ReceiptText,
  RefreshCw,
  Repeat2,
  Trash2,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { InsightBanner } from "@/components/InsightBanner";
import { SpendingChart } from "@/components/SpendingChart";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ACTIVE_PROFILE_EVENT } from "@/lib/active-profile";
import { api, ApiError } from "@/lib/api";
import {
  amountToKurus,
  formatDateTR,
  formatKurus,
  formatPercentTR,
  formatTransactionAmount,
  transactionAmountToKurus,
} from "@/lib/format";
import { cn } from "@/lib/utils";
import type {
  BillingCycle,
  Category,
  CategoryCreateInput,
  ProactiveInsight,
  RecurrenceUnit,
  Subscription,
  SubscriptionCreateInput,
  Transaction,
  TransactionCreateInput,
  TransactionSummary,
  TransactionType,
} from "@/lib/types";

type DashboardView = "overview" | "transactions";

type DashboardClientProps = {
  view?: DashboardView;
};

const DASHBOARD_TABS: Array<{
  href: string;
  view: DashboardView;
  label: string;
  helper: string;
}> = [
  {
    href: "/dashboard",
    view: "overview",
    label: "Özet",
    helper: "Grafikler ve eğilimler",
  },
  {
    href: "/dashboard/transactions",
    view: "transactions",
    label: "İşlemler",
    helper: "Tek seferlik ve tekrarlayan",
  },
];

const selectClassName =
  "flex h-11 w-full rounded-2xl border border-input bg-background/80 px-4 py-2 text-sm ring-offset-background transition-all duration-200 ease-quint focus-visible:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

const billingCycleLabels: Record<BillingCycle, string> = {
  weekly: "Haftalık",
  monthly: "Aylık",
  yearly: "Yıllık",
  custom: "Özel",
};

const recurrenceUnitLabels: Record<RecurrenceUnit, string> = {
  day: "Gün",
  week: "Hafta",
  month: "Ay",
  year: "Yıl",
};

const insightSeverityLabels: Record<ProactiveInsight["severity"], string> = {
  info: "Proaktif koç",
  warning: "Dikkat",
  critical: "Öncelikli uyarı",
};

function insightHref(insight: ProactiveInsight): string {
  if (insight.insight_type === "upcoming_recurring" || insight.action_label?.includes("Tekrar")) {
    return "/dashboard/transactions";
  }
  if (
    insight.insight_type === "receipt_activity" ||
    insight.action_label?.toLocaleLowerCase("tr-TR").includes("fiş")
  ) {
    return "/receipts";
  }
  if (insight.action_label?.includes("İşlem")) {
    return "/dashboard/transactions";
  }
  return "/dashboard";
}

function defaultDateTimeLocal(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function toIsoDateTime(value: string): string {
  return new Date(value).toISOString();
}

function normalizeAmountInput(value: string): string {
  return value.replace(/\./g, "").replace(",", ".");
}

function isValidAmount(value: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(value);
}

function isCurrentMonth(value: string): boolean {
  const date = new Date(value);
  const now = new Date();
  return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth();
}

function sortCategories(categories: Category[]): Category[] {
  return [...categories].sort((first, second) => {
    const ownership = Number(first.user_id !== null) - Number(second.user_id !== null);
    if (ownership !== 0) return ownership;
    return first.name.localeCompare(second.name, "tr");
  });
}

function friendlyError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

function percentValue(value: string | null): number | null {
  if (value === null) return null;
  const parsed = Number(value.replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function TrendBadge({
  value,
  increaseLabel,
  decreaseLabel,
}: {
  value: string | null;
  increaseLabel: string;
  decreaseLabel: string;
}) {
  const numeric = percentValue(value);
  if (numeric === null) {
    return (
      <span className="inline-flex rounded-full bg-muted px-3 py-1 text-xs font-bold text-foreground/80">
        Geçen ay verisi yok
      </span>
    );
  }

  if (numeric === 0) {
    return (
      <span className="inline-flex rounded-full bg-secondary px-3 py-1 text-xs font-bold text-secondary-foreground">
        Geçen ayla aynı
      </span>
    );
  }

  const Icon = numeric > 0 ? ArrowUpRight : ArrowDownRight;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-background/85 px-3 py-1 text-xs font-bold text-foreground">
      <Icon className="h-3.5 w-3.5" />
      {formatPercentTR(value)} · {numeric > 0 ? increaseLabel : decreaseLabel}
    </span>
  );
}

function ErrorNote({ children }: { children: string }) {
  return (
    <p className="bg-destructive/14 rounded-2xl border border-destructive/35 px-4 py-3 text-sm font-semibold text-foreground shadow-sm">
      {children}
    </p>
  );
}

function SummaryStatus({ summary }: { summary: TransactionSummary | null }) {
  const currentIncome = amountToKurus(summary?.income ?? "0");
  const currentExpense = amountToKurus(summary?.expense ?? "0");
  const previousIncome = amountToKurus(summary?.previous_income ?? "0");
  const previousExpense = amountToKurus(summary?.previous_expense ?? "0");
  const maxAmount = Math.max(currentIncome, currentExpense, previousIncome, previousExpense, 1);
  const bars = [
    ["Bu ay gelir", currentIncome, "oklch(var(--primary))"],
    ["Bu ay gider", currentExpense, "oklch(var(--accent))"],
    ["Geçen ay gelir", previousIncome, "oklch(var(--primary) / 0.45)"],
    ["Geçen ay gider", previousExpense, "oklch(var(--accent) / 0.45)"],
  ] as const;

  return (
    <section className="ledger-sheet binder-holes p-5 pl-8 sm:p-8 sm:pl-16">
      <div className="relative z-10 space-y-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="eyebrow">Aylık durum penceresi</p>
            <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
              Gelir ve gider akışı
            </h2>
          </div>
          <span className="stamp-label bg-background/80">Canlı özet</span>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="bg-background/78 rounded-[1.75rem] p-4 sm:p-5">
            <p className="text-sm font-bold text-muted-foreground">Gider eğilimi</p>
            <p className="mt-3 break-words font-display text-[2rem] font-black tabular-nums leading-none sm:text-3xl">
              {formatKurus(currentExpense)}
            </p>
            <div className="mt-4">
              <TrendBadge
                value={summary?.expense_change_percent ?? null}
                increaseLabel="gider arttı"
                decreaseLabel="gider azaldı"
              />
            </div>
          </div>
          <div className="bg-background/78 rounded-[1.75rem] p-4 sm:p-5">
            <p className="text-sm font-bold text-muted-foreground">Gelir eğilimi</p>
            <p className="mt-3 break-words font-display text-[2rem] font-black tabular-nums leading-none sm:text-3xl">
              {formatKurus(currentIncome)}
            </p>
            <div className="mt-4">
              <TrendBadge
                value={summary?.income_change_percent ?? null}
                increaseLabel="gelir arttı"
                decreaseLabel="gelir azaldı"
              />
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {bars.map(([label, value, color]) => (
            <div key={label} className="grid gap-2 sm:grid-cols-[8rem_1fr_7rem] sm:items-center">
              <p className="text-sm font-bold text-muted-foreground">{label}</p>
              <div className="h-3 overflow-hidden rounded-full bg-background/80">
                <div
                  className="h-full rounded-full"
                  style={{ width: `${(value / maxAmount) * 100}%`, backgroundColor: color }}
                />
              </div>
              <p className="font-display text-sm font-black tabular-nums sm:text-right">
                {formatKurus(value)}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function RecurringBars({ subscriptions }: { subscriptions: Subscription[] }) {
  const active = subscriptions.filter((subscription) => subscription.is_active);
  const maxAmount = Math.max(
    ...active.map((subscription) => amountToKurus(subscription.monthly_equivalent)),
    1,
  );

  if (active.length === 0) {
    return (
      <div className="bg-background/72 rounded-[1.75rem] border border-dashed border-primary/30 p-5">
        <p className="font-display text-xl font-black">Tekrarlayan ödeme grafiği boş</p>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          Aktif abonelik veya fatura eklediğinde aylık etkileri çubuk grafik olarak görünecek.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {active.map((subscription) => {
        const monthly = amountToKurus(subscription.monthly_equivalent);
        return (
          <div key={subscription.id} className="space-y-2">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-bold">{subscription.name}</span>
              <span className="font-display font-black tabular-nums">{formatKurus(monthly)}</span>
            </div>
            <div className="h-3 overflow-hidden rounded-full bg-background/80">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${(monthly / maxAmount) * 100}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function DashboardTabs({ activeView }: { activeView: DashboardView }) {
  return (
    <nav
      aria-label="Panel bölümleri"
      className="bg-card/82 grid gap-2 overflow-hidden rounded-[1.5rem] border border-border/70 p-2 shadow-sm sm:grid-cols-2 sm:rounded-[2rem]"
    >
      {DASHBOARD_TABS.map((tab) => {
        const isActive = tab.view === activeView;
        return (
          <Link
            key={tab.view}
            href={tab.href}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "rounded-[1.2rem] px-3 py-3 transition-all duration-200 ease-quint sm:rounded-[1.5rem] sm:px-4",
              isActive
                ? "bg-primary text-primary-foreground shadow-lg shadow-primary/10"
                : "text-muted-foreground hover:bg-muted/70 hover:text-foreground",
            )}
          >
            <span className="font-display text-lg font-black">{tab.label}</span>
            <span className="mt-1 block text-xs font-medium opacity-80">{tab.helper}</span>
          </Link>
        );
      })}
    </nav>
  );
}

export function DashboardClient({ view = "overview" }: DashboardClientProps) {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [summary, setSummary] = useState<TransactionSummary | null>(null);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [insights, setInsights] = useState<ProactiveInsight[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCreatingCategory, setIsCreatingCategory] = useState(false);
  const [isAddingSubscription, setIsAddingSubscription] = useState(false);
  const [isRefreshingInsights, setIsRefreshingInsights] = useState(false);
  const [updatingSubscriptionId, setUpdatingSubscriptionId] = useState<string | null>(null);
  const [dismissingInsightId, setDismissingInsightId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [type, setType] = useState<TransactionType>("expense");
  const [entryMode, setEntryMode] = useState<"one_time" | "recurring">("one_time");
  const [amount, setAmount] = useState("");
  const [merchant, setMerchant] = useState("");
  const [description, setDescription] = useState("");
  const [occurredAt, setOccurredAt] = useState(defaultDateTimeLocal);
  const [categoryId, setCategoryId] = useState("");
  const [newCategoryName, setNewCategoryName] = useState("");
  const [subscriptionName, setSubscriptionName] = useState("");
  const [subscriptionMerchant, setSubscriptionMerchant] = useState("");
  const [subscriptionAmount, setSubscriptionAmount] = useState("");
  const [subscriptionCycle, setSubscriptionCycle] = useState<BillingCycle>("monthly");
  const [subscriptionInterval, setSubscriptionInterval] = useState("1");
  const [subscriptionUnit, setSubscriptionUnit] = useState<RecurrenceUnit>("month");
  const [subscriptionNextDate, setSubscriptionNextDate] = useState("");
  const [subscriptionCategoryId, setSubscriptionCategoryId] = useState("");

  const loadDashboardData = useCallback(async () => {
    setError(null);
    try {
      const [transactionData, categoryData, summaryData, subscriptionData, insightData] =
        await Promise.all([
          api<Transaction[]>("/api/transactions", { silent: true }),
          api<Category[]>("/api/categories", { silent: true }),
          api<TransactionSummary>("/api/transactions/summary", { silent: true }),
          api<Subscription[]>("/api/subscriptions", { silent: true }),
          api<ProactiveInsight[]>("/api/insights", { silent: true }),
        ]);
      setTransactions(transactionData);
      setCategories(sortCategories(categoryData));
      setSummary(summaryData);
      setSubscriptions(subscriptionData);
      setInsights(insightData);
    } catch (err) {
      setError(friendlyError(err, "Bütçe verileri yüklenemedi, biraz sonra tekrar dener misin?"));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboardData();
  }, [loadDashboardData]);

  useEffect(() => {
    function handleActiveProfileChange() {
      setIsLoading(true);
      void loadDashboardData();
    }

    window.addEventListener(ACTIVE_PROFILE_EVENT, handleActiveProfileChange);
    window.addEventListener("storage", handleActiveProfileChange);
    return () => {
      window.removeEventListener(ACTIVE_PROFILE_EVENT, handleActiveProfileChange);
      window.removeEventListener("storage", handleActiveProfileChange);
    };
  }, [loadDashboardData]);

  const refreshSummary = useCallback(async () => {
    const nextSummary = await api<TransactionSummary>("/api/transactions/summary", {
      silent: true,
    });
    setSummary(nextSummary);
  }, []);

  const refreshInsights = useCallback(async () => {
    const nextInsights = await api<ProactiveInsight[]>("/api/insights/refresh", {
      method: "POST",
      silent: true,
    });
    setInsights(nextInsights);
  }, []);

  const categoryNameById = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories],
  );

  const monthly = useMemo(
    () => transactions.filter((tx) => isCurrentMonth(tx.occurred_at)),
    [transactions],
  );
  const fallbackExpense = monthly
    .filter((tx) => tx.type === "expense")
    .reduce((total, tx) => total + Math.abs(transactionAmountToKurus(tx.amount, tx.type)), 0);
  const fallbackIncome = monthly
    .filter((tx) => tx.type === "income")
    .reduce((total, tx) => total + transactionAmountToKurus(tx.amount, tx.type), 0);
  const fallbackBalance = monthly.reduce(
    (total, tx) => total + transactionAmountToKurus(tx.amount, tx.type),
    0,
  );
  const monthlyExpense = summary ? amountToKurus(summary.expense) : fallbackExpense;
  const monthlyIncome = summary ? amountToKurus(summary.income) : fallbackIncome;
  const balance = summary ? amountToKurus(summary.balance) : fallbackBalance;
  const recurringMonthlyTotal = subscriptions
    .filter((subscription) => subscription.is_active)
    .reduce((total, subscription) => total + amountToKurus(subscription.monthly_equivalent), 0);
  const primaryInsight = insights[0] ?? null;
  const visibleInsightCount = insights.length;

  async function handleRefreshInsights() {
    setIsRefreshingInsights(true);
    setError(null);
    try {
      await refreshInsights();
    } catch (err) {
      setError(friendlyError(err, "Koç notları yenilenemedi, tekrar dener misin?"));
    } finally {
      setIsRefreshingInsights(false);
    }
  }

  async function handleDismissInsight(insightId: string) {
    setDismissingInsightId(insightId);
    setError(null);
    try {
      await api<ProactiveInsight>(`/api/insights/${insightId}/dismiss`, {
        method: "PATCH",
        silent: true,
      });
      setInsights((current) => current.filter((insight) => insight.id !== insightId));
    } catch (err) {
      setError(friendlyError(err, "Koç notu kapatılamadı, tekrar dener misin?"));
    } finally {
      setDismissingInsightId(null);
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    const normalizedAmount = normalizeAmountInput(amount);
    if (!isValidAmount(normalizedAmount)) {
      setError("Tutarı 1250,50 biçiminde girer misin?");
      setIsSubmitting(false);
      return;
    }
    const payload: TransactionCreateInput = {
      amount: normalizedAmount,
      type,
      category_id: categoryId || null,
      merchant: merchant || null,
      description: description || null,
      occurred_at: toIsoDateTime(occurredAt),
    };

    try {
      const created = await api<Transaction>("/api/transactions", {
        method: "POST",
        body: payload,
        silent: true,
      });
      setTransactions((current) => [created, ...current]);
      setAmount("");
      setMerchant("");
      setDescription("");
      setOccurredAt(defaultDateTimeLocal());
      await refreshSummary();
      void refreshInsights().catch(() => undefined);
    } catch (err) {
      setError(friendlyError(err, "İşlem kaydedilemedi, tekrar dener misin?"));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateCategory() {
    const name = newCategoryName.trim();
    if (name.length < 2) {
      setError("Kategori adı en az iki karakter olmalı.");
      return;
    }

    setError(null);
    setIsCreatingCategory(true);
    const payload: CategoryCreateInput = { name };
    try {
      const created = await api<Category>("/api/categories", {
        method: "POST",
        body: payload,
        silent: true,
      });
      const createdName = created.name.toLocaleLowerCase("tr-TR");
      setCategories((current) =>
        sortCategories([
          ...current.filter(
            (category) =>
              category.id !== created.id &&
              !(
                category.user_id === null &&
                category.name.toLocaleLowerCase("tr-TR") === createdName
              ),
          ),
          created,
        ]),
      );
      setCategoryId(created.id);
      setSubscriptionCategoryId(created.id);
      setNewCategoryName("");
    } catch (err) {
      setError(friendlyError(err, "Kategori eklenemedi, tekrar dener misin?"));
    } finally {
      setIsCreatingCategory(false);
    }
  }

  async function handleDelete(transactionId: string) {
    setError(null);
    try {
      await api<void>(`/api/transactions/${transactionId}`, { method: "DELETE", silent: true });
      setTransactions((current) => current.filter((tx) => tx.id !== transactionId));
      await refreshSummary();
      void refreshInsights().catch(() => undefined);
    } catch (err) {
      setError(friendlyError(err, "İşlem silinemedi, tekrar dener misin?"));
    }
  }

  async function handleCreateSubscription(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsAddingSubscription(true);
    const normalizedAmount = normalizeAmountInput(subscriptionAmount);
    if (!isValidAmount(normalizedAmount)) {
      setError("Tekrarlayan ödeme tutarını 1250,50 biçiminde girer misin?");
      setIsAddingSubscription(false);
      return;
    }
    const recurrenceInterval = Number.parseInt(subscriptionInterval, 10);
    if (
      subscriptionCycle === "custom" &&
      (!Number.isFinite(recurrenceInterval) || recurrenceInterval < 1)
    ) {
      setError("Özel tekrar aralığını 1 veya daha büyük bir sayı olarak girer misin?");
      setIsAddingSubscription(false);
      return;
    }
    const payload: SubscriptionCreateInput = {
      name: subscriptionName,
      merchant: subscriptionMerchant || null,
      amount: normalizedAmount,
      billing_cycle: subscriptionCycle,
      recurrence_interval: subscriptionCycle === "custom" ? recurrenceInterval : null,
      recurrence_unit: subscriptionCycle === "custom" ? subscriptionUnit : null,
      next_billing_date: subscriptionNextDate || null,
      category_id: subscriptionCategoryId || null,
      is_active: true,
    };

    try {
      const created = await api<Subscription>("/api/subscriptions", {
        method: "POST",
        body: payload,
        silent: true,
      });
      setSubscriptions((current) => [created, ...current]);
      setSubscriptionName("");
      setSubscriptionMerchant("");
      setSubscriptionAmount("");
      setSubscriptionCycle("monthly");
      setSubscriptionInterval("1");
      setSubscriptionUnit("month");
      setSubscriptionNextDate("");
      void refreshInsights().catch(() => undefined);
    } catch (err) {
      setError(friendlyError(err, "Tekrarlayan ödeme kaydedilemedi, tekrar dener misin?"));
    } finally {
      setIsAddingSubscription(false);
    }
  }

  async function handleToggleSubscription(subscription: Subscription) {
    setUpdatingSubscriptionId(subscription.id);
    setError(null);
    try {
      const updated = await api<Subscription>(`/api/subscriptions/${subscription.id}`, {
        method: "PATCH",
        body: { is_active: !subscription.is_active },
        silent: true,
      });
      setSubscriptions((current) =>
        current.map((item) => (item.id === subscription.id ? updated : item)),
      );
      void refreshInsights().catch(() => undefined);
    } catch (err) {
      setError(friendlyError(err, "Durum güncellenemedi, tekrar dener misin?"));
    } finally {
      setUpdatingSubscriptionId(null);
    }
  }

  async function handleDeleteSubscription(subscriptionId: string) {
    setUpdatingSubscriptionId(subscriptionId);
    setError(null);
    try {
      await api<void>(`/api/subscriptions/${subscriptionId}`, {
        method: "DELETE",
        silent: true,
      });
      setSubscriptions((current) => current.filter((item) => item.id !== subscriptionId));
      void refreshInsights().catch(() => undefined);
    } catch (err) {
      setError(friendlyError(err, "Tekrarlayan ödeme silinemedi, tekrar dener misin?"));
    } finally {
      setUpdatingSubscriptionId(null);
    }
  }

  function handleSubscriptionCycleChange(nextCycle: BillingCycle) {
    setSubscriptionCycle(nextCycle);
    if (nextCycle === "weekly") {
      setSubscriptionInterval("1");
      setSubscriptionUnit("week");
    } else if (nextCycle === "yearly") {
      setSubscriptionInterval("1");
      setSubscriptionUnit("year");
    } else {
      setSubscriptionInterval("1");
      setSubscriptionUnit("month");
    }
  }

  return (
    <div className="page-enter space-y-8">
      <DashboardTabs activeView={view} />

      {view === "overview" ? (
        <>
          <section className="grid min-w-0 gap-5 2xl:grid-cols-[1.15fr_0.85fr] 2xl:items-stretch">
            <div className="ledger-sheet binder-holes p-5 pl-8 sm:p-9 sm:pl-20">
              <div className="relative z-10 max-w-4xl space-y-6">
                <span className="stamp-label bg-background/70">Gerçek veri defteri</span>
                <div className="space-y-4">
                  <h1 className="font-display text-[2.7rem] font-black leading-[0.92] sm:text-5xl lg:text-6xl 2xl:text-7xl">
                    Bütçe sayfası artık kategorili.
                  </h1>
                  <p className="text-foreground/78 max-w-[62ch] text-base leading-7 sm:text-lg sm:leading-8">
                    Özet burada kalır; tek seferlik işlem ve tekrarlayan ödeme girişi aynı İşlemler
                    ekranından yönetilir. Böylece kayıt ekleme akışı tek yerde kalır.
                  </p>
                </div>
              </div>
            </div>

            <InsightBanner
              title={
                primaryInsight
                  ? primaryInsight.title
                  : isLoading
                    ? "Koç notu hazırlanıyor"
                    : "Şu an yeni uyarı yok"
              }
              label={
                primaryInsight ? insightSeverityLabels[primaryInsight.severity] : "Proaktif koç"
              }
            >
              {isLoading ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Güncel hareketler okunuyor.</span>
                </div>
              ) : primaryInsight ? (
                <div className="space-y-4">
                  <p>{primaryInsight.content}</p>
                  {visibleInsightCount > 1 ? (
                    <p className="text-xs font-bold text-foreground">
                      {visibleInsightCount - 1} ek koç notu hazır.
                    </p>
                  ) : null}
                  <div className="flex flex-wrap gap-2">
                    {primaryInsight.action_label ? (
                      <Button asChild size="sm">
                        <Link href={insightHref(primaryInsight)}>
                          {primaryInsight.action_label}
                          <ArrowRight className="h-4 w-4" />
                        </Link>
                      </Button>
                    ) : null}
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={handleRefreshInsights}
                      disabled={isRefreshingInsights}
                    >
                      {isRefreshingInsights ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <RefreshCw className="h-4 w-4" />
                      )}
                      Yenile
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => void handleDismissInsight(primaryInsight.id)}
                      disabled={dismissingInsightId === primaryInsight.id}
                    >
                      {dismissingInsightId === primaryInsight.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <XCircle className="h-4 w-4" />
                      )}
                      Kapat
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <p>Yeni işlem, fiş veya tekrarlayan ödeme geldikçe koç buraya uyarı çıkarır.</p>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={handleRefreshInsights}
                    disabled={isRefreshingInsights}
                  >
                    {isRefreshingInsights ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <RefreshCw className="h-4 w-4" />
                    )}
                    Yeniden tara
                  </Button>
                </div>
              )}
            </InsightBanner>
          </section>

          <div className="grid min-w-0 gap-4 md:grid-cols-2 2xl:grid-cols-4">
            {[
              ["Bu ay gider", formatKurus(monthlyExpense), "Kategorili gider toplamı"],
              ["Bu ay gelir", formatKurus(monthlyIncome), "Veritabanındaki gelir toplamı"],
              ["Net durum", formatKurus(balance), "Gelir eksi gider"],
              ["Aylık tekrar", formatKurus(recurringMonthlyTotal), "Aktif abonelik ve faturalar"],
            ].map(([label, value, detail], index) => (
              <div key={label} className="cash-envelope min-h-40 p-4 sm:min-h-44 sm:p-5">
                <div className="relative z-10 flex h-full flex-col justify-between gap-6">
                  <p className="text-sm font-bold text-secondary-foreground/80">{label}</p>
                  <div>
                    <p className="break-words font-display text-[2.15rem] font-black tabular-nums leading-none sm:text-4xl">
                      {value}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
                  </div>
                  <span className="font-display text-xs font-bold text-primary/70">
                    ZARF {index + 1}
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="grid min-w-0 gap-6 2xl:grid-cols-[1.05fr_0.95fr]">
            <SummaryStatus summary={summary} />
            <SpendingChart summary={summary} />
          </div>
        </>
      ) : null}

      {view === "transactions" ? (
        <div className="grid min-w-0 gap-6 2xl:grid-cols-[minmax(27rem,0.72fr)_minmax(38rem,1.28fr)]">
          <section className="ledger-sheet p-5 sm:p-8">
            <div className="relative z-10 space-y-6">
              <div>
                <p className="eyebrow">Kayıt girişi</p>
                <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
                  Yeni kayıt ekle
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Tek seferlik gelir/gider veya tekrarlayan ödeme aynı ekrandan eklenir.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2 rounded-[1.5rem] border border-border/70 bg-background/70 p-2">
                {(
                  [
                    ["one_time", "Tek seferlik", ReceiptText],
                    ["recurring", "Tekrarlayan", Repeat2],
                  ] as const
                ).map(([mode, label, Icon]) => {
                  const isActive = entryMode === mode;
                  return (
                    <button
                      key={mode}
                      type="button"
                      className={cn(
                        "flex min-h-12 items-center justify-center gap-2 rounded-[1.1rem] text-sm font-bold transition-all duration-200 ease-quint",
                        isActive
                          ? "bg-primary text-primary-foreground shadow-sm"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground",
                      )}
                      onClick={() => setEntryMode(mode)}
                    >
                      <Icon className="h-4 w-4" />
                      {label}
                    </button>
                  );
                })}
              </div>

              <div className="bg-background/72 rounded-[1.5rem] border border-dashed border-primary/30 p-3">
                <label htmlFor="new-category-name" className="text-sm font-medium">
                  Yeni kategori
                </label>
                <div className="mt-2 grid gap-2 sm:grid-cols-[1fr_auto]">
                  <Input
                    id="new-category-name"
                    value={newCategoryName}
                    onChange={(event) => setNewCategoryName(event.target.value)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") {
                        event.preventDefault();
                        void handleCreateCategory();
                      }
                    }}
                    placeholder="Kategori adı"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    className="min-h-11"
                    disabled={isCreatingCategory}
                    onClick={() => void handleCreateCategory()}
                  >
                    {isCreatingCategory ? "Ekleniyor..." : "Ekle"}
                  </Button>
                </div>
              </div>

              {entryMode === "one_time" ? (
                <form className="space-y-4" onSubmit={handleSubmit}>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                      <label htmlFor="transaction-type" className="text-sm font-medium">
                        Tür
                      </label>
                      <select
                        id="transaction-type"
                        className={selectClassName}
                        value={type}
                        onChange={(event) => setType(event.target.value as TransactionType)}
                      >
                        <option value="expense">Gider</option>
                        <option value="income">Gelir</option>
                      </select>
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="transaction-amount" className="text-sm font-medium">
                        Tutar
                      </label>
                      <Input
                        id="transaction-amount"
                        inputMode="decimal"
                        placeholder="Tutar gir"
                        value={amount}
                        onChange={(event) => setAmount(event.target.value)}
                        required
                      />
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                      <label htmlFor="transaction-category" className="text-sm font-medium">
                        Kategori
                      </label>
                      <select
                        id="transaction-category"
                        className={selectClassName}
                        value={categoryId}
                        onChange={(event) => setCategoryId(event.target.value)}
                      >
                        <option value="">Kategori seçme</option>
                        {categories.map((category) => (
                          <option key={category.id} value={category.id}>
                            {category.name}
                            {category.user_id ? " · özel" : ""}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="transaction-date" className="text-sm font-medium">
                        Tarih ve saat
                      </label>
                      <Input
                        id="transaction-date"
                        type="datetime-local"
                        value={occurredAt}
                        onChange={(event) => setOccurredAt(event.target.value)}
                        required
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label htmlFor="transaction-merchant" className="text-sm font-medium">
                      Satıcı veya kaynak
                    </label>
                    <Input
                      id="transaction-merchant"
                      value={merchant}
                      onChange={(event) => setMerchant(event.target.value)}
                      placeholder="İsteğe bağlı"
                    />
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="transaction-description" className="text-sm font-medium">
                      Not
                    </label>
                    <Input
                      id="transaction-description"
                      value={description}
                      onChange={(event) => setDescription(event.target.value)}
                      placeholder="Kısa açıklama"
                    />
                  </div>
                  <Button type="submit" className="w-full" disabled={isSubmitting}>
                    {isSubmitting ? "Kaydediliyor..." : "Tek seferlik kaydı ekle"}
                    <Plus className="h-4 w-4" />
                  </Button>
                </form>
              ) : (
                <form className="space-y-4" onSubmit={handleCreateSubscription}>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                      <label htmlFor="subscription-name" className="text-sm font-medium">
                        Ad
                      </label>
                      <Input
                        id="subscription-name"
                        value={subscriptionName}
                        onChange={(event) => setSubscriptionName(event.target.value)}
                        placeholder="Ödeme adı"
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="subscription-amount" className="text-sm font-medium">
                        Tutar
                      </label>
                      <Input
                        id="subscription-amount"
                        inputMode="decimal"
                        value={subscriptionAmount}
                        onChange={(event) => setSubscriptionAmount(event.target.value)}
                        placeholder="Tutar gir"
                        required
                      />
                    </div>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                      <label htmlFor="subscription-cycle" className="text-sm font-medium">
                        Yenilenme
                      </label>
                      <select
                        id="subscription-cycle"
                        className={selectClassName}
                        value={subscriptionCycle}
                        onChange={(event) =>
                          handleSubscriptionCycleChange(event.target.value as BillingCycle)
                        }
                      >
                        <option value="weekly">Haftalık</option>
                        <option value="monthly">Aylık</option>
                        <option value="yearly">Yıllık</option>
                        <option value="custom">Özel</option>
                      </select>
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="subscription-next-date" className="text-sm font-medium">
                        Sonraki tarih
                      </label>
                      <Input
                        id="subscription-next-date"
                        type="date"
                        value={subscriptionNextDate}
                        onChange={(event) => setSubscriptionNextDate(event.target.value)}
                      />
                    </div>
                  </div>

                  {subscriptionCycle === "custom" ? (
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-2">
                        <label htmlFor="subscription-interval" className="text-sm font-medium">
                          Tekrar aralığı
                        </label>
                        <Input
                          id="subscription-interval"
                          type="number"
                          min={1}
                          value={subscriptionInterval}
                          onChange={(event) => setSubscriptionInterval(event.target.value)}
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <label htmlFor="subscription-unit" className="text-sm font-medium">
                          Aralık birimi
                        </label>
                        <select
                          id="subscription-unit"
                          className={selectClassName}
                          value={subscriptionUnit}
                          onChange={(event) =>
                            setSubscriptionUnit(event.target.value as RecurrenceUnit)
                          }
                        >
                          {Object.entries(recurrenceUnitLabels).map(([value, label]) => (
                            <option key={value} value={value}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  ) : null}

                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                      <label htmlFor="subscription-category" className="text-sm font-medium">
                        Kategori
                      </label>
                      <select
                        id="subscription-category"
                        className={selectClassName}
                        value={subscriptionCategoryId}
                        onChange={(event) => setSubscriptionCategoryId(event.target.value)}
                      >
                        <option value="">Kategori seçme</option>
                        {categories.map((category) => (
                          <option key={category.id} value={category.id}>
                            {category.name}
                            {category.user_id ? " · özel" : ""}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="subscription-merchant" className="text-sm font-medium">
                        Kurum veya satıcı
                      </label>
                      <Input
                        id="subscription-merchant"
                        value={subscriptionMerchant}
                        onChange={(event) => setSubscriptionMerchant(event.target.value)}
                        placeholder="İsteğe bağlı"
                      />
                    </div>
                  </div>

                  <Button type="submit" className="w-full" disabled={isAddingSubscription}>
                    {isAddingSubscription ? "Kaydediliyor..." : "Tekrarlayan kaydı ekle"}
                    <Plus className="h-4 w-4" />
                  </Button>
                </form>
              )}
            </div>
          </section>

          <section className="space-y-6">
            {error ? <ErrorNote>{error}</ErrorNote> : null}

            <div className="receipt-tape p-6 pt-9">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="eyebrow">Tekrarlayan aylık etki</p>
                  <h3 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
                    {formatKurus(recurringMonthlyTotal)}
                  </h3>
                </div>
                <span className="stamp-label bg-background/80">Toplam</span>
              </div>
              <div className="mt-6">
                <RecurringBars subscriptions={subscriptions} />
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="eyebrow">Veritabanı kayıtları</p>
                  <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
                    Son işlemler
                  </h2>
                </div>
                <ReceiptText className="h-6 w-6 text-primary" />
              </div>

              {isLoading ? (
                <div className="receipt-tape flex items-center gap-3 px-5 py-6 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  İşlemler yükleniyor...
                </div>
              ) : transactions.length === 0 ? (
                <div className="receipt-tape px-5 py-8">
                  <CalendarDays className="h-6 w-6 text-primary" />
                  <h3 className="mt-4 font-display text-2xl font-black">Henüz işlem yok</h3>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    İlk gerçek gelir veya giderini eklediğinde bu bölüm veritabanından dolacak.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {transactions.map((item) => {
                    const categoryName = item.category_id
                      ? (categoryNameById.get(item.category_id) ?? "Kategori")
                      : "Kategorisiz";
                    return (
                      <div
                        key={item.id}
                        className="receipt-tape flex flex-col gap-4 px-5 py-6 transition-transform duration-300 ease-quint motion-safe:hover:-rotate-1 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div className="min-w-0">
                          <p className="font-display text-lg font-black">
                            {item.merchant ?? item.description ?? "İsimsiz işlem"}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {item.type === "income" ? "Gelir" : "Gider"} / {categoryName} /{" "}
                            {formatDateTR(item.occurred_at)}
                          </p>
                          {item.description && item.description !== item.merchant ? (
                            <p className="mt-1 text-xs text-muted-foreground">{item.description}</p>
                          ) : null}
                        </div>
                        <div className="flex w-full shrink-0 items-center justify-between gap-3 sm:w-auto sm:text-right">
                          <div>
                            <p className="break-words font-display text-xl font-black tabular-nums">
                              {formatTransactionAmount(item.amount, item.type)}
                            </p>
                            <p className="text-xs font-bold text-muted-foreground">
                              {item.source === "manual" ? "Manuel" : "Otomatik"}
                            </p>
                          </div>
                          <Button
                            type="button"
                            variant="ghost"
                            size="icon"
                            aria-label="İşlemi sil"
                            onClick={() => void handleDelete(item.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="eyebrow">Yenilenen kayıtlar</p>
                  <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
                    Tekrarlayan ödemeler
                  </h2>
                </div>
                <Repeat2 className="h-6 w-6 text-primary" />
              </div>

              {subscriptions.length === 0 ? (
                <div className="receipt-tape px-5 py-8">
                  <Repeat2 className="h-6 w-6 text-primary" />
                  <h3 className="mt-4 font-display text-2xl font-black">Tekrarlayan ödeme yok</h3>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Abonelik veya fatura eklediğinde tekil tutarlar ve aylık toplam burada görünür.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {subscriptions.map((subscription) => {
                    const categoryName = subscription.category_id
                      ? (categoryNameById.get(subscription.category_id) ?? "Kategori")
                      : "Kategorisiz";
                    const isUpdating = updatingSubscriptionId === subscription.id;
                    return (
                      <div key={subscription.id} className="receipt-tape px-5 py-6">
                        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                          <div className="min-w-0">
                            <p className="font-display text-lg font-black">{subscription.name}</p>
                            <p className="text-sm text-muted-foreground">
                              {subscription.recurrence_label ||
                                billingCycleLabels[subscription.billing_cycle]}{" "}
                              / {categoryName}
                              {subscription.next_billing_date
                                ? ` / ${formatDateTR(subscription.next_billing_date)}`
                                : ""}
                            </p>
                            {subscription.merchant ? (
                              <p className="mt-1 text-xs text-muted-foreground">
                                {subscription.merchant}
                              </p>
                            ) : null}
                          </div>
                          <div className="shrink-0 sm:text-right">
                            <p className="break-words font-display text-xl font-black tabular-nums">
                              {formatKurus(amountToKurus(subscription.amount))}
                            </p>
                            <p className="text-xs font-bold text-muted-foreground">
                              Aylık etki{" "}
                              {formatKurus(amountToKurus(subscription.monthly_equivalent))}
                            </p>
                          </div>
                        </div>
                        <div className="mt-4 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
                          <Button
                            type="button"
                            variant={subscription.is_active ? "secondary" : "outline"}
                            size="sm"
                            className="min-h-11"
                            disabled={isUpdating}
                            onClick={() => void handleToggleSubscription(subscription)}
                          >
                            {subscription.is_active ? "Pasifleştir" : "Aktifleştir"}
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="min-h-11"
                            disabled={isUpdating}
                            onClick={() => void handleDeleteSubscription(subscription.id)}
                          >
                            Sil
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        </div>
      ) : null}
    </div>
  );
}
