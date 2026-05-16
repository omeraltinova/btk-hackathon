"use client";

import {
  ArrowDownRight,
  ArrowUpRight,
  CalendarDays,
  Edit3,
  Loader2,
  ReceiptText,
  Repeat2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { DashboardTabs } from "@/components/dashboard-client";
import { TransactionEditDialog } from "@/components/TransactionEditDialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ACTIVE_PROFILE_EVENT } from "@/lib/active-profile";
import { api, ApiError } from "@/lib/api";
import { categoriesForType } from "@/lib/category-groups";
import { amountToKurus, formatDateTR, formatKurus, formatTransactionAmount } from "@/lib/format";
import {
  subscriptionLatestIncrease,
  subscriptionPaidTotal,
  subscriptionPaymentHistory,
} from "@/lib/recurring-analysis";
import type {
  Category,
  Subscription,
  Transaction,
  TransactionType,
  TransactionUpdateInput,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const chartColors = [
  "oklch(var(--primary))",
  "oklch(var(--accent))",
  "oklch(0.64 0.1 192)",
  "oklch(0.68 0.12 25)",
  "oklch(0.62 0.11 310)",
  "oklch(0.58 0.13 52)",
];

type CategoryPoint = {
  name: string;
  value: number;
  valueFormatted: string;
  percent: number;
};

type DateRange = {
  start: string;
  end: string;
};

type DateRangePreset = "this_month" | "last_month" | "last_3_months" | "all";

const dateRangePresets: Array<{ key: DateRangePreset; label: string }> = [
  { key: "this_month", label: "Bu ay" },
  { key: "last_month", label: "Geçen ay" },
  { key: "last_3_months", label: "Son 3 ay" },
  { key: "all", label: "Tüm kayıtlar" },
];

const datePartFormatter = new Intl.DateTimeFormat("tr-TR", {
  timeZone: "Europe/Istanbul",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

function friendlyError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

function monthKey(value: string): string {
  return istanbulDateKey(value).slice(0, 7);
}

function monthLabel(key: string): string {
  const [year = "", month = "01"] = key.split("-");
  return new Intl.DateTimeFormat("tr-TR", { month: "long", year: "numeric" }).format(
    new Date(Number(year), Number(month) - 1, 1),
  );
}

function chartColor(index: number): string {
  return chartColors[index % chartColors.length] ?? "oklch(var(--primary))";
}

function padDatePart(value: number): string {
  return String(value).padStart(2, "0");
}

function dateKey(year: number, month: number, day: number): string {
  return `${year}-${padDatePart(month)}-${padDatePart(day)}`;
}

function dateKeyParts(value: string): { year: number; month: number; day: number } {
  const [year = "0", month = "1", day = "1"] = value.split("-");
  return { year: Number(year), month: Number(month), day: Number(day) };
}

function dateInputValue(value: Date): string {
  return dateKey(value.getFullYear(), value.getMonth() + 1, value.getDate());
}

function endOfMonth(year: number, month: number): string {
  return dateKey(year, month, new Date(year, month, 0).getDate());
}

function istanbulDateKey(value: string | Date): string {
  const parts = datePartFormatter.formatToParts(
    typeof value === "string" ? new Date(value) : value,
  );
  const year = parts.find((part) => part.type === "year")?.value ?? "0000";
  const month = parts.find((part) => part.type === "month")?.value ?? "01";
  const day = parts.find((part) => part.type === "day")?.value ?? "01";
  return `${year}-${month}-${day}`;
}

function dateRangeForPreset(preset: DateRangePreset): DateRange {
  const now = new Date();
  const today = dateKeyParts(istanbulDateKey(now));
  if (preset === "all") {
    return { start: "", end: "" };
  }
  if (preset === "last_month") {
    const previousMonth = new Date(today.year, today.month - 2, 1);
    const year = previousMonth.getFullYear();
    const month = previousMonth.getMonth() + 1;
    return { start: dateKey(year, month, 1), end: endOfMonth(year, month) };
  }
  if (preset === "last_3_months") {
    const start = new Date(today.year, today.month - 3, 1);
    return { start: dateInputValue(start), end: endOfMonth(today.year, today.month) };
  }
  return {
    start: dateKey(today.year, today.month, 1),
    end: endOfMonth(today.year, today.month),
  };
}

function formatDateKeyTR(value: string): string {
  const { year, month, day } = dateKeyParts(value);
  return `${padDatePart(day)}.${padDatePart(month)}.${year}`;
}

function dateRangeSummary(range: DateRange): string {
  if (!range.start && !range.end) return "Tüm kayıtlar";
  if (range.start && range.end)
    return `${formatDateKeyTR(range.start)} - ${formatDateKeyTR(range.end)}`;
  if (range.start) return `${formatDateKeyTR(range.start)} sonrası`;
  return `${formatDateKeyTR(range.end)} öncesi`;
}

function rangesEqual(left: DateRange, right: DateRange): boolean {
  return left.start === right.start && left.end === right.end;
}

function transactionInDateRange(transaction: Transaction, range: DateRange): boolean {
  const occurredDate = istanbulDateKey(transaction.occurred_at);
  return (!range.start || occurredDate >= range.start) && (!range.end || occurredDate <= range.end);
}

function categoryName(categoryNameById: Map<string, string>, transaction: Transaction): string {
  return transaction.category_id
    ? (categoryNameById.get(transaction.category_id) ?? "Kategori")
    : "Kategorisiz";
}

function CategoryTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: CategoryPoint }>;
}) {
  if (!active || !payload?.[0]) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-2xl border border-border/80 bg-card px-4 py-3 text-sm shadow-xl">
      <p className="font-display text-base font-black">{point.name}</p>
      <p className="mt-1 font-semibold">{point.valueFormatted}</p>
      <p className="text-muted-foreground">Dağılım payı %{point.percent}</p>
    </div>
  );
}

export function IncomeExpenseClient() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [activeType, setActiveType] = useState<TransactionType>("expense");
  const [dateRange, setDateRange] = useState<DateRange>(() => dateRangeForPreset("this_month"));
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string | null>(null);
  const [editedTransactionId, setEditedTransactionId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [transactionData, categoryData, subscriptionData] = await Promise.all([
        api<Transaction[]>("/api/transactions?limit=100", { silent: true }),
        api<Category[]>("/api/categories", { silent: true }),
        api<Subscription[]>("/api/subscriptions", { silent: true }),
      ]);
      setTransactions(transactionData);
      setCategories(categoryData);
      setSubscriptions(subscriptionData);
    } catch (err) {
      setError(friendlyError(err, "Gelir/gider detayları yüklenemedi, tekrar dener misin?"));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    function handleActiveProfileChange() {
      setIsLoading(true);
      setSelectedSubscriptionId(null);
      setEditedTransactionId(null);
      void loadData();
    }

    window.addEventListener(ACTIVE_PROFILE_EVENT, handleActiveProfileChange);
    window.addEventListener("storage", handleActiveProfileChange);
    return () => {
      window.removeEventListener(ACTIVE_PROFILE_EVENT, handleActiveProfileChange);
      window.removeEventListener("storage", handleActiveProfileChange);
    };
  }, [loadData]);

  const categoryNameById = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories],
  );
  const visibleCategories = useMemo(
    () => categoriesForType(categories, activeType).map((category) => category.name),
    [activeType, categories],
  );
  const hasInvalidDateRange = Boolean(
    dateRange.start && dateRange.end && dateRange.start > dateRange.end,
  );
  const rangeSummary = hasInvalidDateRange ? "Tarih aralığını düzelt" : dateRangeSummary(dateRange);
  const rangeTransactions = useMemo(
    () =>
      hasInvalidDateRange
        ? []
        : transactions.filter((transaction) => transactionInDateRange(transaction, dateRange)),
    [dateRange, hasInvalidDateRange, transactions],
  );
  const typedTransactions = useMemo(
    () => transactions.filter((transaction) => transaction.type === activeType),
    [activeType, transactions],
  );
  const rangeTypedTransactions = useMemo(
    () => rangeTransactions.filter((transaction) => transaction.type === activeType),
    [activeType, rangeTransactions],
  );
  const totalSelectedRange = rangeTypedTransactions.reduce(
    (total, transaction) => total + amountToKurus(transaction.amount),
    0,
  );
  const totalAllTime = typedTransactions.reduce(
    (total, transaction) => total + amountToKurus(transaction.amount),
    0,
  );
  const nextMonthEstimate = subscriptions
    .filter((subscription) => subscription.is_active)
    .reduce((total, subscription) => total + amountToKurus(subscription.monthly_equivalent), 0);
  const monthlyRows = useMemo(() => {
    const rows = new Map<string, { income: number; expense: number }>();
    for (const transaction of rangeTransactions) {
      const key = monthKey(transaction.occurred_at);
      const current = rows.get(key) ?? { income: 0, expense: 0 };
      if (transaction.type === "income") {
        current.income += amountToKurus(transaction.amount);
      } else {
        current.expense += amountToKurus(transaction.amount);
      }
      rows.set(key, current);
    }
    return [...rows.entries()]
      .sort(([left], [right]) => right.localeCompare(left))
      .slice(0, 6)
      .map(([key, value]) => ({
        key,
        label: monthLabel(key),
        income: value.income,
        expense: value.expense,
        net: value.income - value.expense,
      }));
  }, [rangeTransactions]);
  const categoryData = useMemo<CategoryPoint[]>(() => {
    const totals = new Map<string, number>();
    for (const transaction of rangeTypedTransactions) {
      const name = categoryName(categoryNameById, transaction);
      totals.set(name, (totals.get(name) ?? 0) + amountToKurus(transaction.amount));
    }
    const total = [...totals.values()].reduce((sum, value) => sum + value, 0);
    return [...totals.entries()]
      .sort((left, right) => right[1] - left[1])
      .map(([name, value]) => ({
        name,
        value,
        valueFormatted: formatKurus(value),
        percent: total === 0 ? 0 : Math.round((value / total) * 100),
      }));
  }, [categoryNameById, rangeTypedTransactions]);
  const selectedSubscription =
    subscriptions.find((subscription) => subscription.id === selectedSubscriptionId) ??
    subscriptions[0] ??
    null;
  const selectedHistory = selectedSubscription
    ? subscriptionPaymentHistory(rangeTransactions, selectedSubscription)
    : [];
  const selectedPaidTotal = selectedSubscription
    ? subscriptionPaidTotal(rangeTransactions, selectedSubscription)
    : 0;
  const selectedIncrease = selectedSubscription
    ? subscriptionLatestIncrease(rangeTransactions, selectedSubscription)
    : null;
  const editedTransaction =
    transactions.find((transaction) => transaction.id === editedTransactionId) ?? null;

  async function handleUpdateTransaction(
    transactionId: string,
    payload: TransactionUpdateInput,
  ): Promise<void> {
    setError(null);
    const updated = await api<Transaction>(`/api/transactions/${transactionId}`, {
      method: "PATCH",
      body: payload,
      silent: true,
    });
    setTransactions((current) =>
      current.map((item) => (item.id === transactionId ? updated : item)),
    );
  }

  return (
    <div className="page-enter space-y-8">
      <DashboardTabs activeView="income-expense" />

      <section className="ledger-sheet binder-holes p-5 pl-8 sm:p-9 sm:pl-20">
        <div className="relative z-10 max-w-5xl space-y-5">
          <span className="stamp-label bg-background/70">Detay defteri</span>
          <h1 className="font-display text-[2.6rem] font-black leading-[0.94] sm:text-5xl lg:text-6xl">
            Gelir ve giderleri ayrı ayrı incele.
          </h1>
          <p className="text-foreground/78 max-w-[68ch] text-base leading-7 sm:text-lg">
            Özet panel kısa kalır; burada dağılımları, tarihli kayıtları ve tekrarlayan ödeme
            geçmişini daha ayrıntılı görebilirsin.
          </p>
        </div>
      </section>

      {error ? (
        <p className="bg-destructive/14 rounded-2xl border border-destructive/35 px-4 py-3 text-sm font-semibold text-foreground shadow-sm">
          {error}
        </p>
      ) : null}

      <div className="grid gap-3 rounded-[1.5rem] border border-border/70 bg-background/70 p-2 sm:grid-cols-2">
        {(
          [
            ["expense", "Giderler", ArrowDownRight],
            ["income", "Gelirler", ArrowUpRight],
          ] as const
        ).map(([type, label, Icon]) => {
          const isActive = activeType === type;
          return (
            <button
              key={type}
              type="button"
              className={cn(
                "flex min-h-12 items-center justify-center gap-2 rounded-[1.1rem] text-sm font-bold transition-all duration-200 ease-quint",
                isActive
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
              onClick={() => setActiveType(type)}
            >
              <Icon className="h-4 w-4" />
              {label}
            </button>
          );
        })}
      </div>

      <section className="receipt-tape p-4 sm:p-5">
        <div className="grid gap-4 lg:grid-cols-[1fr_auto] lg:items-end">
          <div>
            <div className="flex items-center gap-2">
              <CalendarDays className="h-4 w-4 text-primary" />
              <p className="eyebrow">Tarih aralığı</p>
            </div>
            <h2 className="mt-2 font-display text-2xl font-black leading-none sm:text-3xl">
              Defterin hangi günlerini görmek istiyorsun?
            </h2>
            <p className="mt-2 text-sm font-semibold text-muted-foreground">{rangeSummary}</p>
            {hasInvalidDateRange ? (
              <p className="bg-destructive/12 mt-2 rounded-2xl border border-destructive/35 px-3 py-2 text-sm font-semibold text-foreground">
                Başlangıç tarihi, bitiş tarihinden sonra olamaz.
              </p>
            ) : null}
          </div>

          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] lg:min-w-[42rem]">
            <div className="space-y-2">
              <label htmlFor="income-expense-start-date" className="text-sm font-bold">
                Başlangıç
              </label>
              <Input
                id="income-expense-start-date"
                type="date"
                value={dateRange.start}
                onChange={(event) =>
                  setDateRange((current) => ({ ...current, start: event.target.value }))
                }
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="income-expense-end-date" className="text-sm font-bold">
                Bitiş
              </label>
              <Input
                id="income-expense-end-date"
                type="date"
                value={dateRange.end}
                onChange={(event) =>
                  setDateRange((current) => ({ ...current, end: event.target.value }))
                }
              />
            </div>
            <div className="flex items-end">
              <Button
                type="button"
                variant="secondary"
                className="w-full"
                onClick={() => setDateRange(dateRangeForPreset("all"))}
              >
                Temizle
              </Button>
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {dateRangePresets.map((preset) => {
            const presetRange = dateRangeForPreset(preset.key);
            const isSelected = rangesEqual(dateRange, presetRange);
            return (
              <button
                key={preset.key}
                type="button"
                className={cn(
                  "rounded-full border px-4 py-2 text-sm font-black transition-all duration-200 ease-quint",
                  isSelected
                    ? "border-primary bg-primary text-primary-foreground shadow-sm"
                    : "border-border/70 bg-background/70 text-muted-foreground hover:border-primary/45 hover:text-foreground",
                )}
                onClick={() => setDateRange(presetRange)}
              >
                {preset.label}
              </button>
            );
          })}
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
        <div className="cash-envelope min-h-36 p-5">
          <p className="text-sm font-bold text-secondary-foreground/80">Seçili aralık</p>
          <p className="mt-6 font-display text-4xl font-black tabular-nums">
            {formatKurus(totalSelectedRange)}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            {activeType === "income" ? "Gelir toplamı" : "Gider toplamı"} / {rangeSummary}
          </p>
        </div>
        <div className="cash-envelope min-h-36 p-5">
          <p className="text-sm font-bold text-secondary-foreground/80">Tüm kayıtlar</p>
          <p className="mt-6 font-display text-4xl font-black tabular-nums">
            {formatKurus(totalAllTime)}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">Son 100 işlem içinde</p>
        </div>
        <div className="cash-envelope min-h-36 p-5">
          <p className="text-sm font-bold text-secondary-foreground/80">Kategori seti</p>
          <p className="mt-6 font-display text-4xl font-black tabular-nums">
            {visibleCategories.length}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            {activeType === "income" ? "Gelire özel seçenek" : "Gidere özel seçenek"}
          </p>
        </div>
        <div className="cash-envelope min-h-36 p-5">
          <p className="text-sm font-bold text-secondary-foreground/80">Gelecek ay tahmini</p>
          <p className="mt-6 font-display text-4xl font-black tabular-nums">
            {formatKurus(nextMonthEstimate)}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            Aktif abonelik/faturalardan yaklaşık; kesin değildir.
          </p>
        </div>
      </div>

      <section className="receipt-tape p-5 pt-8 sm:p-6 sm:pt-9">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="eyebrow">Ay ay ayrım</p>
            <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
              Gelir, gider ve net durum
            </h2>
          </div>
          <span className="stamp-label bg-background/80">
            {dateRange.start || dateRange.end ? "Seçili aralık" : "Son 6 ay"}
          </span>
        </div>

        <div className="mt-6 space-y-3">
          {monthlyRows.length === 0 ? (
            <div className="bg-background/72 rounded-[2rem] border border-dashed border-primary/30 p-6">
              <p className="font-display text-xl font-black">Aylık ayrım için kayıt yok</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Seçili tarihlerde gelir veya gider yok. Aralığı genişletebilir ya da yeni kayıt
                ekleyebilirsin.
              </p>
            </div>
          ) : (
            monthlyRows.map((row) => (
              <div
                key={row.key}
                className="grid gap-3 rounded-[1.4rem] border border-border/70 bg-background/70 px-4 py-4 md:grid-cols-[1.2fr_1fr_1fr_1fr] md:items-center"
              >
                <p className="font-display text-lg font-black capitalize">{row.label}</p>
                <p className="text-sm font-bold text-muted-foreground">
                  Gelir{" "}
                  <span className="block font-display text-lg text-foreground">
                    {formatKurus(row.income)}
                  </span>
                </p>
                <p className="text-sm font-bold text-muted-foreground">
                  Gider{" "}
                  <span className="block font-display text-lg text-foreground">
                    {formatKurus(row.expense)}
                  </span>
                </p>
                <p className="text-sm font-bold text-muted-foreground">
                  Net{" "}
                  <span className="block font-display text-lg text-foreground">
                    {formatKurus(row.net)}
                  </span>
                </p>
              </div>
            ))
          )}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <section className="receipt-tape p-5 pt-8 sm:p-6 sm:pt-9">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Seçili aralık</p>
              <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
                Kategori dağılımı
              </h2>
              <p className="mt-2 text-sm font-semibold text-muted-foreground">{rangeSummary}</p>
            </div>
            <ReceiptText className="h-6 w-6 text-primary" />
          </div>

          {isLoading ? (
            <div className="mt-8 flex items-center gap-3 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Detaylar yükleniyor...
            </div>
          ) : categoryData.length === 0 ? (
            <div className="bg-background/72 mt-8 rounded-[2rem] border border-dashed border-primary/30 p-6">
              <p className="font-display text-xl font-black">Dağılım için kayıt yok</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Seçili tarihlerde {activeType === "income" ? "gelir" : "gider"} yok. Aralığı
                değiştirdiğinde grafik de birlikte güncellenir.
              </p>
            </div>
          ) : (
            <div className="mt-6 grid gap-5 lg:grid-cols-[15rem_1fr] lg:items-center">
              <div className="h-60 min-w-0">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={categoryData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={58}
                      outerRadius={104}
                      paddingAngle={2}
                      stroke="oklch(var(--card))"
                      strokeWidth={2}
                    >
                      {categoryData.map((point, index) => (
                        <Cell key={point.name} fill={chartColor(index)} />
                      ))}
                    </Pie>
                    <Tooltip content={<CategoryTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-2">
                {categoryData.map((point, index) => (
                  <div
                    key={point.name}
                    className="flex items-center justify-between gap-3 rounded-2xl bg-background/70 px-4 py-3"
                  >
                    <span className="flex min-w-0 items-center gap-3">
                      <span
                        className="h-3 w-3 shrink-0 rounded-full"
                        style={{ backgroundColor: chartColor(index) }}
                      />
                      <span className="truncate text-sm font-bold">{point.name}</span>
                    </span>
                    <span className="font-display text-sm font-black tabular-nums">
                      {point.valueFormatted} / %{point.percent}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </section>

        <section className="receipt-tape p-5 pt-8 sm:p-6 sm:pt-9">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Tarihli liste</p>
              <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
                Kayıt ayrıntıları
              </h2>
              <p className="mt-2 text-sm font-semibold text-muted-foreground">{rangeSummary}</p>
            </div>
            <span className="stamp-label bg-background/80">Düzenlenebilir</span>
          </div>

          <div className="mt-6 max-h-[31rem] space-y-3 overflow-y-auto pr-1">
            {rangeTypedTransactions.length === 0 ? (
              <div className="bg-background/72 rounded-[2rem] border border-dashed border-primary/30 p-6">
                <p className="font-display text-xl font-black">Kayıt yok</p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Seçili tarihlerde bu türde kayıt yok. Farklı bir aralık seçebilir ya da yeni
                  gelir/gider ekleyebilirsin.
                </p>
              </div>
            ) : (
              rangeTypedTransactions.map((transaction) => (
                <div
                  key={transaction.id}
                  className="rounded-[1.4rem] border border-border/70 bg-background/70 px-4 py-4"
                >
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <p className="truncate font-display text-lg font-black">
                        {transaction.merchant ?? transaction.description ?? "İsimsiz işlem"}
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {formatDateTR(transaction.occurred_at)} /{" "}
                        {categoryName(categoryNameById, transaction)}
                      </p>
                    </div>
                    <div className="flex items-center justify-between gap-3 sm:justify-end">
                      <p className="font-display text-xl font-black tabular-nums">
                        {formatTransactionAmount(transaction.amount, transaction.type)}
                      </p>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label="İşlemi düzenle"
                        onClick={() => setEditedTransactionId(transaction.id)}
                      >
                        <Edit3 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>

      <section className="ledger-sheet p-5 sm:p-8">
        <div className="relative z-10 space-y-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="eyebrow">Tekrarlayan ödeme analizi</p>
              <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
                Geçmiş ödeme ve artış özeti
              </h2>
              <p className="mt-2 text-sm font-semibold text-muted-foreground">{rangeSummary}</p>
            </div>
            <Repeat2 className="h-6 w-6 text-primary" />
          </div>

          <div className="grid gap-4 xl:grid-cols-[0.82fr_1.18fr]">
            <div className="space-y-2">
              {subscriptions.length === 0 ? (
                <div className="receipt-tape px-5 py-6">
                  <p className="font-display text-xl font-black">Tekrarlayan kayıt yok</p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Abonelik eklediğinde geçmiş ödeme tahmini burada görünür.
                  </p>
                </div>
              ) : (
                subscriptions.map((subscription) => {
                  const isSelected = selectedSubscription?.id === subscription.id;
                  const paid = subscriptionPaidTotal(rangeTransactions, subscription);
                  return (
                    <button
                      key={subscription.id}
                      type="button"
                      className={cn(
                        "w-full rounded-[1.25rem] border p-4 text-left transition-all duration-200 ease-quint",
                        isSelected
                          ? "border-primary bg-primary/10 shadow-sm"
                          : "border-border/70 bg-card/70 hover:border-primary/45",
                      )}
                      onClick={() => setSelectedSubscriptionId(subscription.id)}
                    >
                      <span className="block font-display text-lg font-black">
                        {subscription.name}
                      </span>
                      <span className="mt-1 block text-sm text-muted-foreground">
                        Bugünkü tutar {formatKurus(amountToKurus(subscription.amount))} / geçmişte
                        eşleşen {formatKurus(paid)}
                      </span>
                    </button>
                  );
                })
              )}
            </div>

            <div className="rounded-[1.75rem] border border-border/70 bg-card/70 p-4">
              {selectedSubscription ? (
                <div className="space-y-5">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="font-display text-2xl font-black">
                        {selectedSubscription.name}
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {selectedSubscription.recurrence_label} / aylık etki{" "}
                        {formatKurus(amountToKurus(selectedSubscription.monthly_equivalent))}
                      </p>
                    </div>
                    <span className="stamp-label bg-background/80">
                      {selectedSubscription.is_active ? "Aktif" : "Pasif"}
                    </span>
                  </div>

                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-2xl bg-background/70 p-4">
                      <p className="text-xs font-bold text-muted-foreground">Geçmiş toplam</p>
                      <p className="mt-2 font-display text-2xl font-black tabular-nums">
                        {formatKurus(selectedPaidTotal)}
                      </p>
                    </div>
                    <div className="rounded-2xl bg-background/70 p-4">
                      <p className="text-xs font-bold text-muted-foreground">Eşleşen ödeme</p>
                      <p className="mt-2 font-display text-2xl font-black tabular-nums">
                        {selectedHistory.length}
                      </p>
                    </div>
                    <div className="rounded-2xl bg-background/70 p-4">
                      <p className="text-xs font-bold text-muted-foreground">Son artış</p>
                      <p className="mt-2 font-display text-2xl font-black tabular-nums">
                        {selectedIncrease === null ? "Yok" : formatKurus(selectedIncrease)}
                      </p>
                    </div>
                  </div>

                  <div className="h-64">
                    {selectedHistory.length === 0 ? (
                      <div className="bg-background/72 grid h-full place-items-center rounded-[1.5rem] border border-dashed border-primary/30 p-5 text-center">
                        <p className="text-sm leading-6 text-muted-foreground">
                          Bu abonelik için geçmiş ödeme eşleşmedi. Aynı satıcı veya benzer tutarla
                          işlem eklediğinde grafik oluşur.
                        </p>
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                          data={[...selectedHistory].reverse().map((transaction) => ({
                            date: formatDateTR(transaction.occurred_at),
                            amount: amountToKurus(transaction.amount),
                            amountFormatted: formatKurus(amountToKurus(transaction.amount)),
                          }))}
                          margin={{ top: 12, right: 16, bottom: 8, left: 0 }}
                        >
                          <CartesianGrid stroke="oklch(var(--border) / 0.55)" vertical={false} />
                          <XAxis dataKey="date" tickLine={false} axisLine={false} fontSize={11} />
                          <YAxis hide />
                          <Tooltip
                            content={({ active, payload }) => {
                              if (!active || !payload?.[0]) return null;
                              const point = payload[0].payload as {
                                date: string;
                                amountFormatted: string;
                              };
                              return (
                                <div className="rounded-2xl border border-border/80 bg-card px-4 py-3 text-sm shadow-xl">
                                  <p className="font-display text-base font-black">{point.date}</p>
                                  <p className="mt-1 font-semibold">{point.amountFormatted}</p>
                                  <p className="text-muted-foreground">Geçmiş ödeme tutarı</p>
                                </div>
                              );
                            }}
                          />
                          <Bar
                            dataKey="amount"
                            fill="oklch(var(--primary))"
                            radius={[10, 10, 0, 0]}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      <TransactionEditDialog
        open={editedTransaction !== null}
        onOpenChange={(open) => {
          if (!open) setEditedTransactionId(null);
        }}
        transaction={editedTransaction}
        categories={categories}
        onSave={handleUpdateTransaction}
      />
    </div>
  );
}
