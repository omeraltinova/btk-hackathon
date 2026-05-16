"use client";

import {
  ArrowRight,
  ArrowDownRight,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  Edit3,
  ImagePlus,
  Loader2,
  PiggyBank,
  Plus,
  ReceiptText,
  RefreshCw,
  Repeat2,
  Sparkles,
  Target,
  Trash2,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { InsightBanner } from "@/components/InsightBanner";
import { ReceiptUploader } from "@/components/ReceiptUploader";
import { SpendingChart } from "@/components/SpendingChart";
import { TransactionEditDialog } from "@/components/TransactionEditDialog";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { ACTIVE_PROFILE_EVENT } from "@/lib/active-profile";
import { api, ApiError } from "@/lib/api";
import { categoriesForType, hasCategoryForType } from "@/lib/category-groups";
import { rememberActiveConversationId, rememberPendingChatMessage } from "@/lib/chat-session";
import { defaultDateTimeLocal, toDateTimeLocal, toIsoDateTime } from "@/lib/datetime";
import { useKidMode } from "@/lib/kid-mode";
import { amountInput, isValidAmount, normalizeAmountInput } from "@/lib/money-input";
import { isPastTransaction, isSubscriptionPaymentCandidate } from "@/lib/recurring-analysis";
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
  SavingGoal,
  SavingGoalProgress,
  Subscription,
  SubscriptionCreateInput,
  SubscriptionUpdateInput,
  TransactionBudgetEnvelope,
  Transaction,
  TransactionCreateInput,
  TransactionUpdateInput,
  TransactionSummary,
  TransactionType,
} from "@/lib/types";

type DashboardView = "overview" | "transactions" | "income-expense";
type EntryMode = "one_time" | "recurring" | "receipt";

type DashboardClientProps = {
  view?: DashboardView;
};

type RecurringManageMode = "single" | "future";

type SubscriptionDraft = {
  name: string;
  merchant: string;
  amount: string;
  billingCycle: BillingCycle;
  recurrenceInterval: string;
  recurrenceUnit: RecurrenceUnit;
  nextBillingDate: string;
  categoryId: string;
  isActive: boolean;
};

type TransactionDraft = {
  amount: string;
  type: TransactionType;
  categoryId: string;
  merchant: string;
  description: string;
  occurredAt: string;
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
  {
    href: "/dashboard/income-expense",
    view: "income-expense",
    label: "Gelir/Gider",
    helper: "Detay ve dağılım",
  },
];

const selectClassName =
  "flex h-11 w-full rounded-2xl border border-input bg-background/80 px-4 py-2 text-sm ring-offset-background transition-all duration-200 ease-quint focus-visible:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

const TRANSACTION_PREVIEW_LIMIT = 5;
const SUBSCRIPTION_PREVIEW_LIMIT = 4;
const RECURRING_BAR_PREVIEW_LIMIT = 4;

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
    return "/dashboard/transactions";
  }
  if (insight.action_label?.includes("İşlem")) {
    return "/dashboard/transactions";
  }
  return "/dashboard";
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

function normalizeLookup(value: string): string {
  return value.trim().toLocaleLowerCase("tr-TR");
}

function findCategoryByInput(categories: Category[], value: string): Category | null {
  const normalized = normalizeLookup(value);
  if (!normalized) return null;
  return categories.find((category) => normalizeLookup(category.name) === normalized) ?? null;
}

function uniqueSuggestions(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const label = value?.trim();
    if (!label) continue;
    const key = normalizeLookup(label);
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(label);
  }
  return result.sort((first, second) => first.localeCompare(second, "tr"));
}

function CategoryNameInput({
  id,
  value,
  categories,
  onValueChange,
  helper,
}: {
  id: string;
  value: string;
  categories: Category[];
  onValueChange: (value: string) => void;
  helper: string;
}) {
  const listId = `${id}-options`;
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="text-sm font-medium">
        Kategori
      </label>
      <Input
        id={id}
        list={listId}
        value={value}
        onChange={(event) => onValueChange(event.target.value)}
        placeholder="Kategori seç veya yeni yaz"
      />
      <datalist id={listId}>
        {categories.map((category) => (
          <option key={category.id} value={category.name} />
        ))}
      </datalist>
      <p className="text-xs leading-5 text-muted-foreground">{helper}</p>
    </div>
  );
}

function subscriptionToDraft(subscription: Subscription): SubscriptionDraft {
  return {
    name: subscription.name,
    merchant: subscription.merchant ?? "",
    amount: amountInput(subscription.amount),
    billingCycle: subscription.billing_cycle,
    recurrenceInterval: String(subscription.recurrence_interval),
    recurrenceUnit: subscription.recurrence_unit,
    nextBillingDate: subscription.next_billing_date ?? "",
    categoryId: subscription.category_id ?? "",
    isActive: subscription.is_active,
  };
}

function transactionToDraft(transaction: Transaction): TransactionDraft {
  return {
    amount: amountInput(transaction.amount),
    type: transaction.type,
    categoryId: transaction.category_id ?? "",
    merchant: transaction.merchant ?? "",
    description: transaction.description ?? "",
    occurredAt: toDateTimeLocal(transaction.occurred_at),
  };
}

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
  if (parsed === null) return "Hedef yok";
  return `%${new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(parsed)} kullanıldı`;
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

function RecurringBars({
  subscriptions,
  limit,
  onShowAll,
}: {
  subscriptions: Subscription[];
  limit?: number;
  onShowAll?: () => void;
}) {
  const active = subscriptions.filter((subscription) => subscription.is_active);
  const visible = typeof limit === "number" ? active.slice(0, limit) : active;
  const hiddenCount = active.length - visible.length;
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
    <div className="space-y-3">
      {visible.map((subscription) => {
        const monthly = amountToKurus(subscription.monthly_equivalent);
        return (
          <div key={subscription.id} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="truncate font-bold">{subscription.name}</span>
              <span className="shrink-0 font-display font-black tabular-nums">
                {formatKurus(monthly)}
              </span>
            </div>
            <div className="h-2.5 overflow-hidden rounded-full bg-background/80">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${(monthly / maxAmount) * 100}%` }}
              />
            </div>
          </div>
        );
      })}
      {hiddenCount > 0 && onShowAll ? (
        <Button type="button" variant="outline" className="w-full" onClick={onShowAll}>
          Tüm etkileri menüde gör
          <ArrowRight className="h-4 w-4" />
          <span className="bg-primary/12 rounded-full px-2 py-0.5 text-xs">+{hiddenCount}</span>
        </Button>
      ) : null}
    </div>
  );
}

function TransactionRow({
  item,
  categoryNameById,
  onEdit,
  onDelete,
}: {
  item: Transaction;
  categoryNameById: Map<string, string>;
  onEdit: (transaction: Transaction) => void;
  onDelete: (transactionId: string) => void;
}) {
  const categoryName = item.category_id
    ? (categoryNameById.get(item.category_id) ?? "Kategori")
    : "Kategorisiz";

  return (
    <div className="receipt-tape flex flex-col gap-3 px-4 py-4 transition-transform duration-300 ease-quint motion-safe:hover:-rotate-1 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <p className="truncate font-display text-base font-black leading-tight sm:text-lg">
          {item.merchant ?? item.description ?? "İsimsiz işlem"}
        </p>
        <p className="mt-0.5 text-xs font-medium text-muted-foreground sm:text-sm">
          {item.type === "income" ? "Gelir" : "Gider"} / {categoryName} /{" "}
          {formatDateTR(item.occurred_at)}
        </p>
        {item.description && item.description !== item.merchant ? (
          <p className="mt-1 text-xs text-muted-foreground">{item.description}</p>
        ) : null}
      </div>
      <div className="flex w-full shrink-0 items-center justify-between gap-3 sm:w-auto sm:text-right">
        <div>
          <p className="break-words font-display text-lg font-black tabular-nums sm:text-xl">
            {formatTransactionAmount(item.amount, item.type)}
          </p>
          <p className="text-[0.7rem] font-bold uppercase tracking-[0.12em] text-muted-foreground">
            {item.source === "manual" ? "Manuel" : "Otomatik"}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-9 w-9"
            aria-label="İşlemi düzenle"
            onClick={() => onEdit(item)}
          >
            <Edit3 className="h-3.5 w-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-9 w-9"
            aria-label="İşlemi sil"
            onClick={() => onDelete(item.id)}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function SubscriptionRow({
  subscription,
  categoryNameById,
  isUpdating,
  onManage,
  onToggle,
  onDelete,
}: {
  subscription: Subscription;
  categoryNameById: Map<string, string>;
  isUpdating: boolean;
  onManage: (subscription: Subscription) => void;
  onToggle: (subscription: Subscription) => void;
  onDelete: (subscriptionId: string) => void;
}) {
  const categoryName = subscription.category_id
    ? (categoryNameById.get(subscription.category_id) ?? "Kategori")
    : "Kategorisiz";

  return (
    <div className="receipt-tape px-4 py-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="truncate font-display text-base font-black leading-tight sm:text-lg">
            {subscription.name}
          </p>
          <p className="mt-0.5 text-xs font-medium text-muted-foreground sm:text-sm">
            {subscription.recurrence_label || billingCycleLabels[subscription.billing_cycle]} /{" "}
            {categoryName}
            {subscription.next_billing_date
              ? ` / ${formatDateTR(subscription.next_billing_date)}`
              : ""}
          </p>
          {subscription.merchant ? (
            <p className="mt-1 text-xs text-muted-foreground">{subscription.merchant}</p>
          ) : null}
        </div>
        <div className="shrink-0 sm:text-right">
          <p className="break-words font-display text-lg font-black tabular-nums sm:text-xl">
            {formatKurus(amountToKurus(subscription.amount))}
          </p>
          <p className="text-xs font-bold text-muted-foreground">
            Aylık etki {formatKurus(amountToKurus(subscription.monthly_equivalent))}
          </p>
        </div>
      </div>
      <div className="mt-3 grid gap-2 sm:flex sm:flex-wrap">
        <Button
          type="button"
          variant="default"
          size="sm"
          className="min-h-9 px-3 text-xs"
          disabled={isUpdating}
          onClick={() => onManage(subscription)}
        >
          Yönet
          <Edit3 className="h-3.5 w-3.5" />
        </Button>
        <Button
          type="button"
          variant={subscription.is_active ? "secondary" : "outline"}
          size="sm"
          className="min-h-9 px-3 text-xs"
          disabled={isUpdating}
          onClick={() => onToggle(subscription)}
        >
          {subscription.is_active ? "Pasifleştir" : "Aktifleştir"}
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="min-h-9 px-3 text-xs"
          disabled={isUpdating}
          onClick={() => onDelete(subscription.id)}
        >
          Sil
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </div>
  );
}

function FullListDialog({
  open,
  onOpenChange,
  title,
  description,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] w-[calc(100vw-1.5rem)] overflow-hidden rounded-[1.5rem] p-4 sm:max-w-5xl sm:p-5">
        <DialogHeader>
          <DialogTitle className="font-display text-3xl font-black">{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <div className="max-h-[68vh] overflow-y-auto pr-1">
          <div className="space-y-2.5">{children}</div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function RecurringManagerDialog({
  open,
  onOpenChange,
  subscription,
  categories,
  transactions,
  categoryNameById,
  onSaveFuture,
  onSaveSinglePayment,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subscription: Subscription | null;
  categories: Category[];
  transactions: Transaction[];
  categoryNameById: Map<string, string>;
  onSaveFuture: (subscription: Subscription, payload: SubscriptionUpdateInput) => Promise<void>;
  onSaveSinglePayment: (transactionId: string, payload: TransactionUpdateInput) => Promise<void>;
}) {
  const [mode, setMode] = useState<RecurringManageMode>("future");
  const [futureDraft, setFutureDraft] = useState<SubscriptionDraft | null>(null);
  const [selectedPaymentId, setSelectedPaymentId] = useState<string | null>(null);
  const [paymentDraft, setPaymentDraft] = useState<TransactionDraft | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const expenseCategories = useMemo(() => categoriesForType(categories, "expense"), [categories]);

  useEffect(() => {
    if (!open || !subscription) return;
    setMode("future");
    setFutureDraft(subscriptionToDraft(subscription));
    setSelectedPaymentId(null);
    setPaymentDraft(null);
    setLocalError(null);
  }, [open, subscription]);

  const { candidatePayments, isFallbackList } = useMemo(() => {
    if (!subscription) return { candidatePayments: [], isFallbackList: false };
    const sameUserPastExpenses = transactions
      .filter(
        (transaction) =>
          transaction.user_id === subscription.user_id &&
          transaction.type === "expense" &&
          isPastTransaction(transaction),
      )
      .sort(
        (left, right) =>
          new Date(right.occurred_at).getTime() - new Date(left.occurred_at).getTime(),
      );
    const matched = sameUserPastExpenses.filter((transaction) =>
      isSubscriptionPaymentCandidate(transaction, subscription),
    );
    return {
      candidatePayments: (matched.length > 0 ? matched : sameUserPastExpenses).slice(0, 8),
      isFallbackList: matched.length === 0,
    };
  }, [subscription, transactions]);

  function handleSelectPayment(transaction: Transaction) {
    setSelectedPaymentId(transaction.id);
    setPaymentDraft(transactionToDraft(transaction));
    setLocalError(null);
  }

  function handleFutureCycleChange(nextCycle: BillingCycle) {
    setFutureDraft((current) => {
      if (!current) return current;
      if (nextCycle === "weekly") {
        return {
          ...current,
          billingCycle: nextCycle,
          recurrenceInterval: "1",
          recurrenceUnit: "week",
        };
      }
      if (nextCycle === "yearly") {
        return {
          ...current,
          billingCycle: nextCycle,
          recurrenceInterval: "1",
          recurrenceUnit: "year",
        };
      }
      return {
        ...current,
        billingCycle: nextCycle,
        recurrenceInterval: "1",
        recurrenceUnit: "month",
      };
    });
  }

  async function handleSaveFuture(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!subscription || !futureDraft) return;
    const normalizedAmount = normalizeAmountInput(futureDraft.amount);
    if (!isValidAmount(normalizedAmount)) {
      setLocalError("Gelecek ödeme tutarını 1250,50 biçiminde girer misin?");
      return;
    }
    const recurrenceInterval = Number.parseInt(futureDraft.recurrenceInterval, 10);
    if (
      futureDraft.billingCycle === "custom" &&
      (!Number.isFinite(recurrenceInterval) || recurrenceInterval < 1)
    ) {
      setLocalError("Gelecek ödemeler için tekrar aralığı 1 veya daha büyük olmalı.");
      return;
    }

    const payload: SubscriptionUpdateInput = {
      name: futureDraft.name,
      merchant: futureDraft.merchant || null,
      amount: normalizedAmount,
      billing_cycle: futureDraft.billingCycle,
      recurrence_interval: futureDraft.billingCycle === "custom" ? recurrenceInterval : null,
      recurrence_unit: futureDraft.billingCycle === "custom" ? futureDraft.recurrenceUnit : null,
      next_billing_date: futureDraft.nextBillingDate || null,
      category_id: futureDraft.categoryId || null,
      is_active: futureDraft.isActive,
    };

    setIsSaving(true);
    setLocalError(null);
    try {
      await onSaveFuture(subscription, payload);
      onOpenChange(false);
    } catch (err) {
      setLocalError(friendlyError(err, "Gelecek ödemeler güncellenemedi, tekrar dener misin?"));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleSaveSinglePayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPaymentId || !paymentDraft) {
      setLocalError("Düzenlemek için bir geçmiş ödeme seç.");
      return;
    }
    const normalizedAmount = normalizeAmountInput(paymentDraft.amount);
    if (!isValidAmount(normalizedAmount)) {
      setLocalError("Geçmiş ödeme tutarını 1250,50 biçiminde girer misin?");
      return;
    }
    if (!paymentDraft.occurredAt) {
      setLocalError("Geçmiş ödeme için tarih ve saat seç.");
      return;
    }

    const payload: TransactionUpdateInput = {
      amount: normalizedAmount,
      type: paymentDraft.type,
      category_id: paymentDraft.categoryId || null,
      merchant: paymentDraft.merchant || null,
      description: paymentDraft.description || null,
      occurred_at: toIsoDateTime(paymentDraft.occurredAt),
    };

    setIsSaving(true);
    setLocalError(null);
    try {
      await onSaveSinglePayment(selectedPaymentId, payload);
      onOpenChange(false);
    } catch (err) {
      setLocalError(friendlyError(err, "Geçmiş ödeme güncellenemedi, tekrar dener misin?"));
    } finally {
      setIsSaving(false);
    }
  }

  if (!subscription || !futureDraft) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] w-[calc(100vw-1.5rem)] overflow-hidden rounded-[1.5rem] p-4 sm:max-w-6xl sm:p-6">
        <DialogHeader>
          <DialogTitle className="font-display text-3xl font-black">
            Tekrarlayan ödemeyi yönet
          </DialogTitle>
          <DialogDescription>
            Tek bir geçmiş ödemeyi düzeltebilir veya gelecekteki tüm yenilemeleri değiştirebilirsin.
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[72vh] overflow-y-auto pr-1">
          <div className="space-y-5">
            <div className="rounded-[1.5rem] border border-border/70 bg-card/75 p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="font-display text-2xl font-black">{subscription.name}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {subscription.recurrence_label ||
                      billingCycleLabels[subscription.billing_cycle]}{" "}
                    / {formatKurus(amountToKurus(subscription.amount))}
                  </p>
                </div>
                <span className="stamp-label bg-background/80">
                  {subscription.is_active ? "Aktif" : "Pasif"}
                </span>
              </div>
            </div>

            <div className="grid gap-2 rounded-[1.5rem] border border-border/70 bg-background/70 p-2 sm:grid-cols-2">
              {(
                [
                  ["future", "Gelecektekilerin tümü", "Abonelik/fatura kuralını değiştir"],
                  ["single", "Geçmiş tek ödeme", "Seçili işlem kaydını düzelt"],
                ] as const
              ).map(([value, label, helper]) => {
                const isActive = mode === value;
                return (
                  <button
                    key={value}
                    type="button"
                    className={cn(
                      "rounded-[1.1rem] px-4 py-3 text-left transition-all duration-200 ease-quint",
                      isActive
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                    onClick={() => {
                      setMode(value);
                      setLocalError(null);
                    }}
                  >
                    <span className="block font-display text-lg font-black">{label}</span>
                    <span className="mt-1 block text-xs font-medium opacity-80">{helper}</span>
                  </button>
                );
              })}
            </div>

            {localError ? <ErrorNote>{localError}</ErrorNote> : null}

            {mode === "future" ? (
              <form className="space-y-4" onSubmit={handleSaveFuture}>
                <div className="bg-background/72 rounded-[1.5rem] border border-dashed border-primary/30 p-4 text-sm leading-6 text-muted-foreground">
                  Bu değişiklik gelecek yenileme planını etkiler; geçmiş işlem kayıtları aynı kalır.
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-2">
                    <label htmlFor="future-subscription-name" className="text-sm font-medium">
                      Ad
                    </label>
                    <Input
                      id="future-subscription-name"
                      value={futureDraft.name}
                      onChange={(event) =>
                        setFutureDraft((current) =>
                          current ? { ...current, name: event.target.value } : current,
                        )
                      }
                      required
                    />
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="future-subscription-amount" className="text-sm font-medium">
                      Tutar
                    </label>
                    <Input
                      id="future-subscription-amount"
                      inputMode="decimal"
                      value={futureDraft.amount}
                      onChange={(event) =>
                        setFutureDraft((current) =>
                          current ? { ...current, amount: event.target.value } : current,
                        )
                      }
                      required
                    />
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-2">
                    <label htmlFor="future-subscription-cycle" className="text-sm font-medium">
                      Yenilenme
                    </label>
                    <select
                      id="future-subscription-cycle"
                      className={selectClassName}
                      value={futureDraft.billingCycle}
                      onChange={(event) =>
                        handleFutureCycleChange(event.target.value as BillingCycle)
                      }
                    >
                      <option value="weekly">Haftalık</option>
                      <option value="monthly">Aylık</option>
                      <option value="yearly">Yıllık</option>
                      <option value="custom">Özel</option>
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="future-subscription-date" className="text-sm font-medium">
                      Sonraki tarih
                    </label>
                    <Input
                      id="future-subscription-date"
                      type="date"
                      value={futureDraft.nextBillingDate}
                      onChange={(event) =>
                        setFutureDraft((current) =>
                          current ? { ...current, nextBillingDate: event.target.value } : current,
                        )
                      }
                    />
                  </div>
                </div>

                {futureDraft.billingCycle === "custom" ? (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-2">
                      <label htmlFor="future-subscription-interval" className="text-sm font-medium">
                        Tekrar aralığı
                      </label>
                      <Input
                        id="future-subscription-interval"
                        type="number"
                        min={1}
                        value={futureDraft.recurrenceInterval}
                        onChange={(event) =>
                          setFutureDraft((current) =>
                            current
                              ? { ...current, recurrenceInterval: event.target.value }
                              : current,
                          )
                        }
                        required
                      />
                    </div>
                    <div className="space-y-2">
                      <label htmlFor="future-subscription-unit" className="text-sm font-medium">
                        Aralık birimi
                      </label>
                      <select
                        id="future-subscription-unit"
                        className={selectClassName}
                        value={futureDraft.recurrenceUnit}
                        onChange={(event) =>
                          setFutureDraft((current) =>
                            current
                              ? {
                                  ...current,
                                  recurrenceUnit: event.target.value as RecurrenceUnit,
                                }
                              : current,
                          )
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
                    <label htmlFor="future-subscription-category" className="text-sm font-medium">
                      Kategori
                    </label>
                    <select
                      id="future-subscription-category"
                      className={selectClassName}
                      value={futureDraft.categoryId}
                      onChange={(event) =>
                        setFutureDraft((current) =>
                          current ? { ...current, categoryId: event.target.value } : current,
                        )
                      }
                    >
                      <option value="">Kategori seçme</option>
                      {expenseCategories.map((category) => (
                        <option key={category.id} value={category.id}>
                          {category.name}
                          {category.user_id ? " · özel" : ""}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-2">
                    <label htmlFor="future-subscription-status" className="text-sm font-medium">
                      Durum
                    </label>
                    <select
                      id="future-subscription-status"
                      className={selectClassName}
                      value={futureDraft.isActive ? "active" : "inactive"}
                      onChange={(event) =>
                        setFutureDraft((current) =>
                          current
                            ? { ...current, isActive: event.target.value === "active" }
                            : current,
                        )
                      }
                    >
                      <option value="active">Aktif</option>
                      <option value="inactive">Pasif</option>
                    </select>
                  </div>
                </div>

                <div className="space-y-2">
                  <label htmlFor="future-subscription-merchant" className="text-sm font-medium">
                    Kurum veya satıcı
                  </label>
                  <Input
                    id="future-subscription-merchant"
                    value={futureDraft.merchant}
                    onChange={(event) =>
                      setFutureDraft((current) =>
                        current ? { ...current, merchant: event.target.value } : current,
                      )
                    }
                    placeholder="İsteğe bağlı"
                  />
                </div>

                <Button type="submit" className="w-full" disabled={isSaving}>
                  {isSaving ? "Kaydediliyor..." : "Gelecekteki tüm ödemeleri güncelle"}
                </Button>
              </form>
            ) : (
              <form className="space-y-4" onSubmit={handleSaveSinglePayment}>
                <div className="bg-background/72 rounded-[1.5rem] border border-dashed border-primary/30 p-4 text-sm leading-6 text-muted-foreground">
                  Bu bölüm yalnızca seçtiğin geçmiş işlem kaydını değiştirir; gelecek ödeme planı
                  aynı kalır.
                </div>

                <div className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-display text-xl font-black">Geçmiş ödeme seç</p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {isFallbackList
                          ? "Benzer kayıt bulunamadı; aynı profile ait son giderler gösteriliyor."
                          : "Bu tekrarlayan kayda benzeyen geçmiş ödemeler."}
                      </p>
                    </div>
                    <span className="stamp-label bg-background/80">
                      {candidatePayments.length} kayıt
                    </span>
                  </div>

                  {candidatePayments.length === 0 ? (
                    <div className="receipt-tape px-5 py-6">
                      <p className="font-display text-xl font-black">Geçmiş ödeme yok</p>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">
                        Önce bu ödeme için bir işlem kaydı eklediğinde burada tek kaydı
                        düzenleyebilirsin.
                      </p>
                    </div>
                  ) : (
                    <div className="grid gap-2 md:grid-cols-2">
                      {candidatePayments.map((transaction) => {
                        const isSelected = selectedPaymentId === transaction.id;
                        const categoryName = transaction.category_id
                          ? (categoryNameById.get(transaction.category_id) ?? "Kategori")
                          : "Kategorisiz";
                        return (
                          <button
                            key={transaction.id}
                            type="button"
                            className={cn(
                              "rounded-[1.25rem] border p-4 text-left transition-all duration-200 ease-quint",
                              isSelected
                                ? "border-primary bg-primary/10 shadow-sm"
                                : "border-border/70 bg-card/70 hover:border-primary/45",
                            )}
                            onClick={() => handleSelectPayment(transaction)}
                          >
                            <span className="block font-display text-lg font-black">
                              {transaction.merchant ?? transaction.description ?? "İsimsiz ödeme"}
                            </span>
                            <span className="mt-1 block text-sm text-muted-foreground">
                              {formatDateTR(transaction.occurred_at)} / {categoryName}
                            </span>
                            <span className="mt-3 block font-display text-xl font-black tabular-nums">
                              {formatTransactionAmount(transaction.amount, transaction.type)}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  )}
                </div>

                {paymentDraft ? (
                  <div className="space-y-4 rounded-[1.5rem] border border-border/70 bg-card/70 p-4">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-2">
                        <label htmlFor="single-payment-amount" className="text-sm font-medium">
                          Tutar
                        </label>
                        <Input
                          id="single-payment-amount"
                          inputMode="decimal"
                          value={paymentDraft.amount}
                          onChange={(event) =>
                            setPaymentDraft((current) =>
                              current ? { ...current, amount: event.target.value } : current,
                            )
                          }
                          required
                        />
                      </div>
                      <div className="space-y-2">
                        <label htmlFor="single-payment-date" className="text-sm font-medium">
                          Tarih ve saat
                        </label>
                        <Input
                          id="single-payment-date"
                          type="datetime-local"
                          value={paymentDraft.occurredAt}
                          onChange={(event) =>
                            setPaymentDraft((current) =>
                              current ? { ...current, occurredAt: event.target.value } : current,
                            )
                          }
                          required
                        />
                      </div>
                    </div>

                    <div className="grid gap-3 sm:grid-cols-2">
                      <div className="space-y-2">
                        <label htmlFor="single-payment-category" className="text-sm font-medium">
                          Kategori
                        </label>
                        <select
                          id="single-payment-category"
                          className={selectClassName}
                          value={paymentDraft.categoryId}
                          onChange={(event) =>
                            setPaymentDraft((current) =>
                              current ? { ...current, categoryId: event.target.value } : current,
                            )
                          }
                        >
                          <option value="">Kategori seçme</option>
                          {expenseCategories.map((category) => (
                            <option key={category.id} value={category.id}>
                              {category.name}
                              {category.user_id ? " · özel" : ""}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-2">
                        <label htmlFor="single-payment-type" className="text-sm font-medium">
                          Tür
                        </label>
                        <select
                          id="single-payment-type"
                          className={selectClassName}
                          value={paymentDraft.type}
                          onChange={(event) =>
                            setPaymentDraft((current) =>
                              current
                                ? { ...current, type: event.target.value as TransactionType }
                                : current,
                            )
                          }
                        >
                          <option value="expense">Gider</option>
                          <option value="income">Gelir</option>
                        </select>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <label htmlFor="single-payment-merchant" className="text-sm font-medium">
                        Satıcı veya kaynak
                      </label>
                      <Input
                        id="single-payment-merchant"
                        value={paymentDraft.merchant}
                        onChange={(event) =>
                          setPaymentDraft((current) =>
                            current ? { ...current, merchant: event.target.value } : current,
                          )
                        }
                        placeholder="İsteğe bağlı"
                      />
                    </div>

                    <div className="space-y-2">
                      <label htmlFor="single-payment-description" className="text-sm font-medium">
                        Not
                      </label>
                      <Input
                        id="single-payment-description"
                        value={paymentDraft.description}
                        onChange={(event) =>
                          setPaymentDraft((current) =>
                            current ? { ...current, description: event.target.value } : current,
                          )
                        }
                        placeholder="Kısa açıklama"
                      />
                    </div>
                  </div>
                ) : null}

                <Button type="submit" className="w-full" disabled={isSaving || !paymentDraft}>
                  {isSaving ? "Kaydediliyor..." : "Seçili geçmiş ödemeyi güncelle"}
                </Button>
              </form>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

const envelopeStatusLabels: Record<TransactionBudgetEnvelope["status"], string> = {
  safe: "Rahat",
  watch: "Dikkat",
  over: "Aşıldı",
};

function goalSummaryTone(goal: SavingGoal) {
  if (goal.goal_type === "accumulation") {
    return {
      badge: "border-primary/40 bg-primary/10 text-primary",
      progress: "bg-primary",
      row: "border-primary/25 bg-primary/10",
      text: "text-primary",
      label: "Birikim",
    };
  }
  return {
    badge: "border-accent/60 bg-accent/25 text-accent-foreground",
    progress: "bg-accent",
    row: "border-accent/40 bg-accent/15",
    text: "text-accent-foreground",
    label: "Tasarruf",
  };
}

function GoalSlider({
  goals,
  progressByGoalId,
  isLoading,
}: {
  goals: SavingGoal[];
  progressByGoalId: Record<string, SavingGoalProgress>;
  isLoading: boolean;
}) {
  const activeGoals = goals.filter((goal) => goal.status === "active");

  return (
    <section className="ledger-sheet p-4 sm:p-5">
      <div className="relative z-10 space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="eyebrow">Hedef rayı</p>
            <h2 className="mt-1 font-display text-2xl font-black leading-none sm:text-[1.7rem]">
              Birikim ve tasarruf
            </h2>
          </div>
          <Button asChild size="sm" variant="secondary" className="w-fit">
            <Link href="/dashboard/goals">
              Hedefleri aç
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center gap-2 rounded-[1.25rem] border border-border/70 bg-background/70 p-3 text-sm font-bold text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Hedefler yükleniyor.
          </div>
        ) : activeGoals.length === 0 ? (
          <p className="rounded-[1.25rem] border border-border/70 bg-background/70 p-3 text-sm font-bold text-muted-foreground">
            Aktif hedef yok. Birikim veya tasarruf hedefi eklediğinde burada kayan liste görünür.
          </p>
        ) : (
          <div className="grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {activeGoals.slice(0, 6).map((goal) => {
              const tone = goalSummaryTone(goal);
              const progress = progressByGoalId[goal.id];
              const progressWidth = progress
                ? Math.max(0, Math.min(100, Number(progress.progress_percent)))
                : 0;
              const remaining =
                goal.goal_type === "accumulation"
                  ? (progress?.remaining_amount ?? goal.target_amount ?? "0")
                  : (progress?.remaining_limit ?? goal.target_spending_amount);
              return (
                <Link
                  key={goal.id}
                  href={`/dashboard/goals?hedef=${encodeURIComponent(goal.id)}`}
                  className={cn(
                    "min-w-0 rounded-[1.25rem] border p-3 transition-transform duration-200 ease-quint hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                    tone.row,
                  )}
                >
                  <span
                    className={cn(
                      "inline-flex rounded-full border px-2.5 py-1 text-[0.68rem] font-black",
                      tone.badge,
                    )}
                  >
                    {tone.label}
                  </span>
                  <p className="mt-2 truncate font-display text-lg font-black">{goal.title}</p>
                  <p className="mt-1 text-xs font-bold text-muted-foreground">
                    {goal.goal_type === "accumulation" ? "Kalan tutar" : goal.category_name}
                  </p>
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-background/80">
                    <div
                      className={cn("h-full rounded-full", tone.progress)}
                      style={{ width: `${progressWidth}%` }}
                    />
                  </div>
                  <p
                    className={cn(
                      "mt-3 truncate font-display text-lg font-black tabular-nums",
                      tone.text,
                    )}
                  >
                    {formatKurus(amountToKurus(remaining))}
                  </p>
                </Link>
              );
            })}
            {activeGoals.length > 6 ? (
              <Link
                href="/dashboard/goals"
                className="grid min-h-32 place-items-center rounded-[1.25rem] border border-dashed border-border/80 bg-background/65 p-3 text-center text-sm font-black text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                +{activeGoals.length - 6} hedef daha
              </Link>
            ) : null}
          </div>
        )}
      </div>
    </section>
  );
}

function BudgetEnvelopeBoard({ summary }: { summary: TransactionSummary | null }) {
  const envelopes = summary?.envelopes ?? [];
  const savingsEnvelope = envelopes.find((envelope) => envelope.is_savings_goal) ?? null;
  const orderedEnvelopes = envelopes
    .map((envelope, index) => ({ envelope, index }))
    .sort((first, second) => {
      const priority = (envelope: TransactionBudgetEnvelope) => {
        if (envelope.status === "over") return 0;
        if (envelope.status === "watch") return 1;
        if (envelope.is_savings_goal) return 2;
        return 3;
      };
      return priority(first.envelope) - priority(second.envelope) || first.index - second.index;
    })
    .map(({ envelope }) => envelope);
  const previewEnvelopes = orderedEnvelopes.slice(0, 4);
  const hiddenEnvelopeCount = Math.max(orderedEnvelopes.length - previewEnvelopes.length, 0);

  function renderEnvelopeRow(envelope: TransactionBudgetEnvelope) {
    const budget = amountToKurus(envelope.budget);
    const spent = amountToKurus(envelope.spent);
    const remaining = amountToKurus(envelope.remaining);
    const safeDailyAmount = amountToKurus(envelope.safe_daily_amount);
    const progress = budget > 0 ? Math.min(100, Math.max(0, (spent / budget) * 100)) : 0;
    const label = envelope.is_savings_goal ? "Birikim" : envelopeStatusLabels[envelope.status];

    return (
      <div
        key={envelope.slug}
        className="rounded-[1.25rem] border border-border/70 bg-background/70 p-3"
      >
        <div className="grid gap-3 sm:grid-cols-[minmax(9rem,0.95fr)_minmax(13rem,1.2fr)_auto] sm:items-center">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href={`/dashboard/goals?zarf=${encodeURIComponent(envelope.slug)}`}
                className={cn(
                  "truncate font-display text-lg font-black transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  envelope.is_savings_goal ? "hover:text-primary" : "hover:text-foreground",
                )}
              >
                {envelope.label}
              </Link>
              <span
                className={cn(
                  "rounded-full px-2.5 py-1 text-[0.68rem] font-black",
                  envelope.is_savings_goal
                    ? "border border-primary/40 bg-primary/10 text-primary"
                    : envelope.status === "over"
                      ? "bg-destructive text-destructive-foreground"
                      : envelope.status === "watch"
                        ? "bg-accent text-accent-foreground"
                        : "border border-border/70 bg-muted text-foreground",
                )}
              >
                {label}
              </span>
            </div>
            <p className="mt-1 text-xs font-bold text-muted-foreground">
              {formatUsedPercent(envelope.used_percent)}
            </p>
          </div>

          <div className="space-y-2">
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div
                className={cn(
                  "h-full rounded-full",
                  envelope.is_savings_goal
                    ? "bg-primary"
                    : envelope.status === "over"
                      ? "bg-destructive"
                      : envelope.status === "watch"
                        ? "bg-accent"
                        : "bg-muted-foreground/45",
                )}
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs font-bold text-muted-foreground">
              <span>Bütçe {formatKurus(budget)}</span>
              <span>Harcanan {formatKurus(spent)}</span>
              <span>
                {envelope.is_savings_goal ? "Günlük hedef" : "Güvenli günlük"}{" "}
                {formatKurus(safeDailyAmount)}
              </span>
            </div>
          </div>

          <div className="sm:text-right">
            <p className="text-xs font-bold text-muted-foreground">Kalan</p>
            <p
              className={cn(
                "font-display text-2xl font-black tabular-nums leading-none",
                remaining < 0 ? "text-destructive" : "text-foreground",
              )}
            >
              {formatKurus(remaining)}
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <section className="ledger-sheet p-4 sm:p-5">
      <div className="relative z-10 space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="eyebrow">Zarf özeti</p>
            <h2 className="mt-1 font-display text-2xl font-black leading-none sm:text-[1.7rem]">
              Aylık sınırlar kısa görünümde
            </h2>
          </div>
          {savingsEnvelope ? (
            <p className="flex items-center gap-2 rounded-full border border-border/70 bg-background/70 px-3 py-2 text-xs font-black text-primary">
              <PiggyBank className="h-4 w-4" />
              Birikim hedefi {formatKurus(amountToKurus(savingsEnvelope.budget))}
            </p>
          ) : null}
        </div>

        {previewEnvelopes.length > 0 ? (
          <div className="grid gap-3">{previewEnvelopes.map(renderEnvelopeRow)}</div>
        ) : (
          <p className="rounded-[1.25rem] border border-border/70 bg-background/70 p-3 text-sm font-bold text-muted-foreground">
            Zarf verisi oluşunca burada kısa bir liste görünür.
          </p>
        )}

        {orderedEnvelopes.length > 0 ? (
          <Button asChild size="sm" variant="secondary" className="w-fit">
            <Link href="/dashboard/goals?sekme=zarflar">
              Tüm zarfları göster
              {hiddenEnvelopeCount > 0 ? ` (+${hiddenEnvelopeCount})` : null}
              <ArrowRight className="h-4 w-4" />
            </Link>
          </Button>
        ) : null}
      </div>
    </section>
  );
}

export function DashboardTabs({ activeView }: { activeView: DashboardView }) {
  return (
    <nav
      aria-label="Panel bölümleri"
      className="bg-card/82 grid gap-2 overflow-hidden rounded-[1.5rem] border border-border/70 p-2 shadow-sm sm:grid-cols-3 sm:rounded-[2rem]"
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
  const router = useRouter();
  const { isKid } = useKidMode();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [summary, setSummary] = useState<TransactionSummary | null>(null);
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [savingGoals, setSavingGoals] = useState<SavingGoal[]>([]);
  const [savingGoalProgress, setSavingGoalProgress] = useState<Record<string, SavingGoalProgress>>(
    {},
  );
  const [insights, setInsights] = useState<ProactiveInsight[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isAddingSubscription, setIsAddingSubscription] = useState(false);
  const [isRefreshingInsights, setIsRefreshingInsights] = useState(false);
  const [updatingSubscriptionId, setUpdatingSubscriptionId] = useState<string | null>(null);
  const [dismissingInsightId, setDismissingInsightId] = useState<string | null>(null);
  const [isTransactionListOpen, setIsTransactionListOpen] = useState(false);
  const [isSubscriptionListOpen, setIsSubscriptionListOpen] = useState(false);
  const [isRecurringImpactOpen, setIsRecurringImpactOpen] = useState(false);
  const [managedSubscriptionId, setManagedSubscriptionId] = useState<string | null>(null);
  const [editedTransactionId, setEditedTransactionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [type, setType] = useState<TransactionType>("expense");
  const [entryMode, setEntryMode] = useState<EntryMode>("one_time");
  const [amount, setAmount] = useState("");
  const [merchant, setMerchant] = useState("");
  const [description, setDescription] = useState("");
  const [occurredAt, setOccurredAt] = useState(defaultDateTimeLocal);
  const [categoryId, setCategoryId] = useState("");
  const [categoryInput, setCategoryInput] = useState("");
  const [subscriptionName, setSubscriptionName] = useState("");
  const [subscriptionMerchant, setSubscriptionMerchant] = useState("");
  const [subscriptionAmount, setSubscriptionAmount] = useState("");
  const [subscriptionCycle, setSubscriptionCycle] = useState<BillingCycle>("monthly");
  const [subscriptionInterval, setSubscriptionInterval] = useState("1");
  const [subscriptionUnit, setSubscriptionUnit] = useState<RecurrenceUnit>("month");
  const [subscriptionNextDate, setSubscriptionNextDate] = useState("");
  const [subscriptionCategoryId, setSubscriptionCategoryId] = useState("");
  const [subscriptionCategoryInput, setSubscriptionCategoryInput] = useState("");

  const loadDashboardData = useCallback(async () => {
    setError(null);
    try {
      const [transactionData, categoryData, summaryData, subscriptionData, goalData, insightData] =
        await Promise.all([
          api<Transaction[]>("/api/transactions", { silent: true }),
          api<Category[]>("/api/categories", { silent: true }),
          api<TransactionSummary>("/api/transactions/summary", { silent: true }),
          api<Subscription[]>("/api/subscriptions", { silent: true }),
          api<SavingGoal[]>("/api/saving-goals?status=active", { silent: true }),
          api<ProactiveInsight[]>("/api/insights", { silent: true }),
        ]);
      setTransactions(transactionData);
      setCategories(sortCategories(categoryData));
      setSummary(summaryData);
      setSubscriptions(subscriptionData);
      setSavingGoals(goalData);
      const progressRows = await Promise.all(
        goalData.map((goal) =>
          api<SavingGoalProgress>(`/api/saving-goals/${goal.id}/progress`, { silent: true }),
        ),
      );
      setSavingGoalProgress(
        Object.fromEntries(progressRows.map((progress) => [progress.goal.id, progress])),
      );
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
  const transactionCategories = useMemo(
    () => categoriesForType(categories, type),
    [categories, type],
  );
  const subscriptionCategories = useMemo(
    () => categoriesForType(categories, "expense"),
    [categories],
  );
  const merchantSuggestions = useMemo(
    () =>
      uniqueSuggestions([
        ...transactions.map((transaction) => transaction.merchant),
        ...subscriptions.map((subscription) => subscription.merchant),
      ]),
    [transactions, subscriptions],
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
  const previewTransactions = transactions.slice(0, TRANSACTION_PREVIEW_LIMIT);
  const hiddenTransactionCount = Math.max(transactions.length - previewTransactions.length, 0);
  const previewSubscriptions = subscriptions.slice(0, SUBSCRIPTION_PREVIEW_LIMIT);
  const hiddenSubscriptionCount = Math.max(subscriptions.length - previewSubscriptions.length, 0);
  const managedSubscription =
    subscriptions.find((subscription) => subscription.id === managedSubscriptionId) ?? null;
  const editedTransaction =
    transactions.find((transaction) => transaction.id === editedTransactionId) ?? null;

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

  function handleStartSmartPlan() {
    rememberPendingChatMessage({
      message:
        "Akıllı hedef planı çıkar. Son harcamalarıma bakıp nereden kısabileceğimi ve hangi birikim hedefini açabileceğimi öner.",
      source: "dashboard",
      title: "Akıllı hedef planı",
      startNew: true,
    });
    rememberActiveConversationId(null);
    router.push("/chat");
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
    if (
      categoryInput.trim().length === 1 &&
      findCategoryByInput(transactionCategories, categoryInput) === null
    ) {
      setError("Yeni kategori adı en az iki karakter olmalı.");
      setIsSubmitting(false);
      return;
    }
    try {
      const resolvedCategoryId = await resolveCategoryId({
        input: categoryInput,
        allowedCategories: transactionCategories,
        currentId: categoryId,
        fallbackType: type,
      });
      const payload: TransactionCreateInput = {
        amount: normalizedAmount,
        type,
        category_id: resolvedCategoryId || null,
        merchant: merchant || null,
        description: description || null,
        occurred_at: toIsoDateTime(occurredAt),
      };
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
      setCategoryInput("");
      setCategoryId("");
      await refreshSummary();
      void refreshInsights().catch(() => undefined);
    } catch (err) {
      setError(friendlyError(err, "İşlem kaydedilemedi, tekrar dener misin?"));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleCreateCategory(nameInput: string): Promise<Category> {
    const name = nameInput.trim();
    if (name.length < 2) {
      setError("Kategori adı en az iki karakter olmalı.");
      throw new Error("Kategori adı en az iki karakter olmalı.");
    }

    setError(null);
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
      return created;
    } catch (err) {
      setError(friendlyError(err, "Kategori eklenemedi, tekrar dener misin?"));
      throw err;
    }
  }

  async function resolveCategoryId({
    input,
    allowedCategories,
    currentId,
    fallbackType,
  }: {
    input: string;
    allowedCategories: Category[];
    currentId: string;
    fallbackType: TransactionType;
  }): Promise<string> {
    const typed = input.trim();
    if (!typed) return "";
    const matched = findCategoryByInput(allowedCategories, typed);
    if (matched) return matched.id;
    if (currentId && hasCategoryForType(categories, currentId, fallbackType)) return currentId;
    const created = await handleCreateCategory(typed);
    return created.id;
  }

  async function handleDelete(transactionId: string) {
    setError(null);
    try {
      await api<void>(`/api/transactions/${transactionId}`, { method: "DELETE", silent: true });
      setTransactions((current) => current.filter((tx) => tx.id !== transactionId));
      setEditedTransactionId((current) => (current === transactionId ? null : current));
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
    if (
      subscriptionCategoryInput.trim().length === 1 &&
      findCategoryByInput(subscriptionCategories, subscriptionCategoryInput) === null
    ) {
      setError("Yeni kategori adı en az iki karakter olmalı.");
      setIsAddingSubscription(false);
      return;
    }
    try {
      const resolvedCategoryId = await resolveCategoryId({
        input: subscriptionCategoryInput,
        allowedCategories: subscriptionCategories,
        currentId: subscriptionCategoryId,
        fallbackType: "expense",
      });
      const payload: SubscriptionCreateInput = {
        name: subscriptionName,
        merchant: subscriptionMerchant || null,
        amount: normalizedAmount,
        billing_cycle: subscriptionCycle,
        recurrence_interval: subscriptionCycle === "custom" ? recurrenceInterval : null,
        recurrence_unit: subscriptionCycle === "custom" ? subscriptionUnit : null,
        next_billing_date: subscriptionNextDate || null,
        category_id: resolvedCategoryId || null,
        is_active: true,
      };
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
      setSubscriptionCategoryId("");
      setSubscriptionCategoryInput("");
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

  async function handleUpdateSubscription(
    subscription: Subscription,
    payload: SubscriptionUpdateInput,
  ) {
    setUpdatingSubscriptionId(subscription.id);
    setError(null);
    try {
      const updated = await api<Subscription>(`/api/subscriptions/${subscription.id}`, {
        method: "PATCH",
        body: payload,
        silent: true,
      });
      setSubscriptions((current) =>
        current.map((item) => (item.id === subscription.id ? updated : item)),
      );
      void refreshInsights().catch(() => undefined);
    } finally {
      setUpdatingSubscriptionId(null);
    }
  }

  async function handleUpdateSinglePayment(transactionId: string, payload: TransactionUpdateInput) {
    setError(null);
    const updated = await api<Transaction>(`/api/transactions/${transactionId}`, {
      method: "PATCH",
      body: payload,
      silent: true,
    });
    setTransactions((current) =>
      current.map((item) => (item.id === transactionId ? updated : item)),
    );
    await refreshSummary();
    void refreshInsights().catch(() => undefined);
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
      setManagedSubscriptionId((current) => (current === subscriptionId ? null : current));
      void refreshInsights().catch(() => undefined);
    } catch (err) {
      setError(friendlyError(err, "Tekrarlayan ödeme silinemedi, tekrar dener misin?"));
    } finally {
      setUpdatingSubscriptionId(null);
    }
  }

  // In kid lite mode recurring payments belong to the parent surface, but receipt
  // scanning remains available as a simple way to add a purchase.
  useEffect(() => {
    if (isKid && entryMode === "recurring") {
      setEntryMode("one_time");
    }
  }, [isKid, entryMode]);

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

  function handleTransactionTypeChange(nextType: TransactionType) {
    setType(nextType);
    if (!hasCategoryForType(categories, categoryId, nextType)) {
      setCategoryId("");
      setCategoryInput("");
    }
  }

  function handleTransactionCategoryInput(nextValue: string) {
    setCategoryInput(nextValue);
    setCategoryId(findCategoryByInput(transactionCategories, nextValue)?.id ?? "");
  }

  function handleSubscriptionCategoryInput(nextValue: string) {
    setSubscriptionCategoryInput(nextValue);
    setSubscriptionCategoryId(findCategoryByInput(subscriptionCategories, nextValue)?.id ?? "");
  }

  function handleReceiptConfirmed(transaction: Transaction) {
    setTransactions((current) => [
      transaction,
      ...current.filter((item) => item.id !== transaction.id),
    ]);
    void refreshSummary();
    void refreshInsights().catch(() => undefined);
  }

  return (
    <div className="page-enter space-y-8">
      <DashboardTabs activeView={view} />

      {view === "overview" ? (
        <>
          <section className="grid min-w-0 gap-5 2xl:grid-cols-[1.15fr_0.85fr] 2xl:items-stretch">
            {isKid ? (
              <div className="kid-balance-bubble flex flex-col gap-4">
                <span className="kid-chip">
                  <PiggyBank className="h-4 w-4" />
                  Kumbaranın özeti
                </span>
                <p className="kid-hero-title">Merhaba! Cüzdanın bugün nasıl görünüyor?</p>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-3xl bg-background/70 p-4">
                    <p className="text-sm font-bold text-muted-foreground">Bu ay kumbarana giren</p>
                    <p className="mt-2 font-display text-3xl font-black tabular-nums text-primary">
                      {formatKurus(monthlyIncome)}
                    </p>
                  </div>
                  <div className="rounded-3xl bg-background/70 p-4">
                    <p className="text-sm font-bold text-muted-foreground">
                      Bu ay kumbarandan çıkan
                    </p>
                    <p className="mt-2 font-display text-3xl font-black tabular-nums text-accent-foreground">
                      {formatKurus(monthlyExpense)}
                    </p>
                  </div>
                </div>
                <p className="text-sm leading-6 text-muted-foreground">
                  Yeni bir harçlık ya da gider eklemek için aşağıdaki Hareketler kartını
                  kullanabilirsin.
                </p>
              </div>
            ) : (
              <div className="ledger-sheet binder-holes p-5 pl-8 sm:p-9 sm:pl-20">
                <div className="relative z-10 max-w-4xl space-y-6">
                  <span className="stamp-label bg-background/70">Gerçek veri defteri</span>
                  <div className="space-y-4">
                    <h1 className="font-display text-[2.7rem] font-black leading-[0.92] sm:text-5xl lg:text-6xl 2xl:text-7xl">
                      Bütçe sayfası artık kategorili.
                    </h1>
                    <p className="text-foreground/78 max-w-[62ch] text-base leading-7 sm:text-lg sm:leading-8">
                      Özet burada kalır; tek seferlik işlem, tekrarlayan ödeme ve fiş tarama aynı
                      İşlemler ekranından yönetilir. Böylece kayıt ekleme akışı tek yerde kalır.
                    </p>
                  </div>
                </div>
              </div>
            )}

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
                    <Button asChild size="sm" variant="secondary">
                      <Link href="/dashboard/goals">
                        Hedef oluştur
                        <Target className="h-4 w-4" />
                      </Link>
                    </Button>
                    <Button asChild size="sm" variant="secondary">
                      <Link href="/learn">
                        Dersi aç
                        <BookOpen className="h-4 w-4" />
                      </Link>
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      onClick={handleStartSmartPlan}
                    >
                      Plan çıkar
                      <Sparkles className="h-4 w-4" />
                    </Button>
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

          <div className="grid min-w-0 gap-4 md:grid-cols-2 2xl:grid-cols-5">
            {(isKid
              ? ([
                  ["Bu ay biriktirdiğin", formatKurus(monthlyIncome), "Harçlık ve hediye toplamı"],
                  ["Bu ay harcadığın", formatKurus(monthlyExpense), "Alışveriş ve eğlence"],
                  ["Cüzdanda kalan", formatKurus(balance), "Biriktirebileceğin tutar"],
                ] as const)
              : ([
                  [
                    "Bu ay bütçelenen",
                    formatKurus(amountToKurus(summary?.budgeted_month ?? "0")),
                    "Zarf limitlerinin toplamı",
                  ],
                  [
                    "Bu ay harcanan",
                    formatKurus(amountToKurus(summary?.spent_month ?? "0")),
                    "Toplam aylık gider",
                  ],
                  [
                    "Kalan bütçe",
                    formatKurus(amountToKurus(summary?.remaining_budget ?? "0")),
                    "Ay sonuna kadar kullanılabilir",
                  ],
                  [
                    "Gelecek ay tahmini",
                    formatKurus(recurringMonthlyTotal),
                    "Aktif tekrarlar; kesinleşmiş borç değildir",
                  ],
                  [
                    "Riskli kategori",
                    summary?.risky_category?.label ?? "Riskli zarf yok",
                    summary?.risky_category
                      ? `${formatKurus(amountToKurus(summary.risky_category.spent))} / ${formatKurus(
                          amountToKurus(summary.risky_category.budget),
                        )}`
                      : "Bütçe aşımı görünmüyor",
                  ],
                ] as const)
            ).map(([label, value, detail]) => (
              <div key={label} className="cash-envelope min-h-40 p-4 sm:min-h-44 sm:p-5">
                <div className="relative z-10 flex h-full flex-col justify-between gap-6">
                  <p className="text-sm font-bold text-secondary-foreground/80">{label}</p>
                  <div>
                    <p className="break-words font-display text-[2.15rem] font-black tabular-nums leading-none sm:text-4xl">
                      {value}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {isKid ? (
            <div className="ledger-sheet p-5 sm:p-7">
              <div className="relative z-10 flex flex-col gap-3">
                <span className="kid-chip">
                  <Sparkles className="h-4 w-4" />
                  Koçun mini önerisi
                </span>
                <p className="font-display text-2xl font-black leading-tight">
                  Para biriktirmek aslında oyun gibi.
                </p>
                <p className="text-sm leading-6 text-muted-foreground">
                  Bir sonraki harçlığında kumbaranın için küçük bir hedef seçmek ister misin? Koç
                  sekmesinden sorabilirsin.
                </p>
                <Button asChild className="w-fit">
                  <Link href="/chat">
                    Koçla sohbet et
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                </Button>
              </div>
            </div>
          ) : (
            <>
              <div className="grid min-w-0 gap-6 2xl:grid-cols-[1fr_1fr]">
                <BudgetEnvelopeBoard summary={summary} />
                <GoalSlider
                  goals={savingGoals}
                  progressByGoalId={savingGoalProgress}
                  isLoading={isLoading}
                />
              </div>
              <div className="grid min-w-0 gap-6 2xl:grid-cols-[1.05fr_0.95fr]">
                <SummaryStatus summary={summary} />
                <SpendingChart summary={summary} />
              </div>
            </>
          )}
        </>
      ) : null}

      {view === "transactions" ? (
        <>
          <div
            className={cn(
              "grid min-w-0 gap-5",
              "2xl:grid-cols-[minmax(25rem,0.68fr)_minmax(39rem,1.32fr)]",
            )}
          >
            <section className="ledger-sheet p-4 sm:p-6">
              <div className="relative z-10 space-y-5">
                <div>
                  <p className="eyebrow">{isKid ? "Yeni hareket" : "Kayıt girişi"}</p>
                  <h2 className="mt-2 font-display text-[1.65rem] font-black leading-none sm:text-2xl">
                    {isKid ? "Bir şey ekleyelim mi?" : "Yeni kayıt ekle"}
                  </h2>
                  <p className="mt-2 text-sm leading-5 text-muted-foreground">
                    {isKid
                      ? "Aldığın harçlığı, yaptığın alışverişi veya fişini bu sayfadan ekleyebilirsin."
                      : "Tek seferlik gelir/gider, tekrarlayan ödeme ve fiş tarama aynı ekrandan eklenir."}
                  </p>
                </div>

                {isKid ? null : (
                  <div
                    className={cn(
                      "grid gap-2 rounded-[1.5rem] border border-border/70 bg-background/70 p-2",
                      isKid ? "grid-cols-2" : "grid-cols-3",
                    )}
                  >
                    {(isKid
                      ? ([
                          ["one_time", "Hareket", ReceiptText],
                          ["receipt", "Fiş tara", ImagePlus],
                        ] as const)
                      : ([
                          ["one_time", "Tek seferlik", ReceiptText],
                          ["recurring", "Tekrarlayan", Repeat2],
                          ["receipt", "Fiş tara", ImagePlus],
                        ] as const)
                    ).map(([mode, label, Icon]) => {
                      const isActive = entryMode === mode;
                      return (
                        <button
                          key={mode}
                          type="button"
                          className={cn(
                            "flex min-h-10 items-center justify-center gap-2 rounded-[1.1rem] text-sm font-bold transition-all duration-200 ease-quint",
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
                )}

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
                          onChange={(event) =>
                            handleTransactionTypeChange(event.target.value as TransactionType)
                          }
                        >
                          <option value="expense">{isKid ? "Harcadım" : "Gider"}</option>
                          <option value="income">{isKid ? "Aldım" : "Gelir"}</option>
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
                      <CategoryNameInput
                        id="transaction-category"
                        value={categoryInput}
                        categories={transactionCategories}
                        onValueChange={handleTransactionCategoryInput}
                        helper="Listeden seçebilir ya da yeni kategori adını yazabilirsin."
                      />
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
                        list="merchant-source-options"
                        value={merchant}
                        onChange={(event) => setMerchant(event.target.value)}
                        placeholder="İsteğe bağlı"
                      />
                      <datalist id="merchant-source-options">
                        {merchantSuggestions.map((suggestion) => (
                          <option key={suggestion} value={suggestion} />
                        ))}
                      </datalist>
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
                ) : entryMode === "recurring" ? (
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
                      <CategoryNameInput
                        id="subscription-category"
                        value={subscriptionCategoryInput}
                        categories={subscriptionCategories}
                        onValueChange={handleSubscriptionCategoryInput}
                        helper="Gider kategorilerinden seç veya yeni bir ad yaz."
                      />
                      <div className="space-y-2">
                        <label htmlFor="subscription-merchant" className="text-sm font-medium">
                          Kurum veya satıcı
                        </label>
                        <Input
                          id="subscription-merchant"
                          list="subscription-merchant-source-options"
                          value={subscriptionMerchant}
                          onChange={(event) => setSubscriptionMerchant(event.target.value)}
                          placeholder="İsteğe bağlı"
                        />
                        <datalist id="subscription-merchant-source-options">
                          {merchantSuggestions.map((suggestion) => (
                            <option key={suggestion} value={suggestion} />
                          ))}
                        </datalist>
                      </div>
                    </div>

                    <Button type="submit" className="w-full" disabled={isAddingSubscription}>
                      {isAddingSubscription ? "Kaydediliyor..." : "Tekrarlayan kaydı ekle"}
                      <Plus className="h-4 w-4" />
                    </Button>
                  </form>
                ) : (
                  <div className="min-w-0">
                    <ReceiptUploader
                      compact
                      showHistory={false}
                      onConfirmed={handleReceiptConfirmed}
                    />
                  </div>
                )}
              </div>
            </section>

            <section className="space-y-5">
              {error ? <ErrorNote>{error}</ErrorNote> : null}

              {isKid ? null : (
                <div className="receipt-tape p-4 pt-6 sm:p-5 sm:pt-7">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="eyebrow">Tekrarlayan aylık etki</p>
                      <h3 className="mt-2 font-display text-[1.65rem] font-black leading-none sm:text-2xl">
                        {formatKurus(recurringMonthlyTotal)}
                      </h3>
                    </div>
                    <span className="stamp-label bg-background/80">Toplam</span>
                  </div>
                  <div className="mt-4">
                    <RecurringBars
                      subscriptions={subscriptions}
                      limit={RECURRING_BAR_PREVIEW_LIMIT}
                      onShowAll={() => setIsRecurringImpactOpen(true)}
                    />
                  </div>
                </div>
              )}

              <div className="space-y-2.5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="eyebrow">Veritabanı kayıtları</p>
                    <h2 className="mt-2 font-display text-[1.65rem] font-black leading-none sm:text-2xl">
                      Son işlemler
                    </h2>
                  </div>
                  <div className="flex items-center gap-2">
                    {hiddenTransactionCount > 0 ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => setIsTransactionListOpen(true)}
                      >
                        Tümünü menüde gör
                        <span className="bg-primary/12 rounded-full px-2 py-0.5 text-xs">
                          +{hiddenTransactionCount}
                        </span>
                      </Button>
                    ) : null}
                    <ReceiptText className="h-5 w-5 text-primary" />
                  </div>
                </div>

                {isLoading ? (
                  <div className="receipt-tape flex items-center gap-3 px-4 py-4 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    İşlemler yükleniyor...
                  </div>
                ) : transactions.length === 0 ? (
                  <div className="receipt-tape px-4 py-6">
                    <CalendarDays className="h-6 w-6 text-primary" />
                    <h3 className="mt-4 font-display text-2xl font-black">Henüz işlem yok</h3>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      İlk gerçek gelir veya giderini eklediğinde bu bölüm veritabanından dolacak.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {previewTransactions.map((item) => (
                      <TransactionRow
                        key={item.id}
                        item={item}
                        categoryNameById={categoryNameById}
                        onEdit={(transaction) => setEditedTransactionId(transaction.id)}
                        onDelete={(transactionId) => void handleDelete(transactionId)}
                      />
                    ))}
                    {hiddenTransactionCount > 0 ? (
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full"
                        onClick={() => setIsTransactionListOpen(true)}
                      >
                        Tüm işlemleri menüde gör
                        <ArrowRight className="h-4 w-4" />
                        <span className="bg-primary/12 rounded-full px-2 py-0.5 text-xs">
                          +{hiddenTransactionCount}
                        </span>
                      </Button>
                    ) : null}
                  </div>
                )}
              </div>

              {isKid ? null : (
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="eyebrow">Yenilenen kayıtlar</p>
                      <h2 className="mt-2 font-display text-[1.65rem] font-black leading-none sm:text-2xl">
                        Tekrarlayan ödemeler
                      </h2>
                    </div>
                    <div className="flex items-center gap-2">
                      {hiddenSubscriptionCount > 0 ? (
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setIsSubscriptionListOpen(true)}
                        >
                          Tümünü menüde gör
                          <span className="bg-primary/12 rounded-full px-2 py-0.5 text-xs">
                            +{hiddenSubscriptionCount}
                          </span>
                        </Button>
                      ) : null}
                      <Repeat2 className="h-5 w-5 text-primary" />
                    </div>
                  </div>

                  {subscriptions.length === 0 ? (
                    <div className="receipt-tape px-4 py-6">
                      <Repeat2 className="h-6 w-6 text-primary" />
                      <h3 className="mt-4 font-display text-2xl font-black">
                        Tekrarlayan ödeme yok
                      </h3>
                      <p className="mt-2 text-sm leading-6 text-muted-foreground">
                        Abonelik veya fatura eklediğinde tekil tutarlar ve aylık toplam burada
                        görünür.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2.5">
                      {previewSubscriptions.map((subscription) => (
                        <SubscriptionRow
                          key={subscription.id}
                          subscription={subscription}
                          categoryNameById={categoryNameById}
                          isUpdating={updatingSubscriptionId === subscription.id}
                          onManage={(item) => setManagedSubscriptionId(item.id)}
                          onToggle={(item) => void handleToggleSubscription(item)}
                          onDelete={(subscriptionId) =>
                            void handleDeleteSubscription(subscriptionId)
                          }
                        />
                      ))}
                      {hiddenSubscriptionCount > 0 ? (
                        <Button
                          type="button"
                          variant="outline"
                          className="w-full"
                          onClick={() => setIsSubscriptionListOpen(true)}
                        >
                          Tüm tekrarlayanları menüde gör
                          <ArrowRight className="h-4 w-4" />
                          <span className="bg-primary/12 rounded-full px-2 py-0.5 text-xs">
                            +{hiddenSubscriptionCount}
                          </span>
                        </Button>
                      ) : null}
                    </div>
                  )}
                </div>
              )}
            </section>
          </div>
        </>
      ) : null}

      <FullListDialog
        open={isTransactionListOpen}
        onOpenChange={setIsTransactionListOpen}
        title="Tüm işlemler"
        description={`Bu profilde görünen ${transactions.length} işlem kaydı.`}
      >
        {transactions.map((item) => (
          <TransactionRow
            key={item.id}
            item={item}
            categoryNameById={categoryNameById}
            onEdit={(transaction) => setEditedTransactionId(transaction.id)}
            onDelete={(transactionId) => void handleDelete(transactionId)}
          />
        ))}
      </FullListDialog>

      <TransactionEditDialog
        open={editedTransaction !== null}
        onOpenChange={(open) => {
          if (!open) setEditedTransactionId(null);
        }}
        transaction={editedTransaction}
        categories={categories}
        onSave={handleUpdateSinglePayment}
      />

      <FullListDialog
        open={isSubscriptionListOpen}
        onOpenChange={setIsSubscriptionListOpen}
        title="Tüm tekrarlayan ödemeler"
        description={`Bu profilde görünen ${subscriptions.length} tekrarlayan kayıt.`}
      >
        {subscriptions.map((subscription) => (
          <SubscriptionRow
            key={subscription.id}
            subscription={subscription}
            categoryNameById={categoryNameById}
            isUpdating={updatingSubscriptionId === subscription.id}
            onManage={(item) => setManagedSubscriptionId(item.id)}
            onToggle={(item) => void handleToggleSubscription(item)}
            onDelete={(subscriptionId) => void handleDeleteSubscription(subscriptionId)}
          />
        ))}
      </FullListDialog>

      <RecurringManagerDialog
        open={managedSubscription !== null}
        onOpenChange={(open) => {
          if (!open) setManagedSubscriptionId(null);
        }}
        subscription={managedSubscription}
        categories={categories}
        transactions={transactions}
        categoryNameById={categoryNameById}
        onSaveFuture={handleUpdateSubscription}
        onSaveSinglePayment={handleUpdateSinglePayment}
      />

      <FullListDialog
        open={isRecurringImpactOpen}
        onOpenChange={setIsRecurringImpactOpen}
        title="Tüm aylık tekrar etkileri"
        description="Aktif tekrarlayan kayıtların aylık bütçeye etkisi."
      >
        <div className="receipt-tape p-4">
          <RecurringBars subscriptions={subscriptions} />
        </div>
      </FullListDialog>
    </div>
  );
}
