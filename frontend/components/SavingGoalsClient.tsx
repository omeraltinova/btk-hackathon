"use client";

import {
  CheckCircle2,
  ListChecks,
  MessageCircle,
  PauseCircle,
  PlayCircle,
  PiggyBank,
  Plus,
  Target,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { type MouseEvent, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { EnvelopeBudgetClient } from "@/components/EnvelopeBudgetClient";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";
import { rememberPendingChatMessage } from "@/lib/chat-session";
import { useKidMode } from "@/lib/kid-mode";
import { isValidAmount, normalizeAmountInput } from "@/lib/money-input";
import type {
  Category,
  SavingGoal,
  SavingGoalProgress,
  SavingGoalUpdateInput,
  Transaction,
} from "@/lib/types";
import { cn } from "@/lib/utils";

type GoalMode = "accumulation" | "expense_reduction";
type GoalSurface = "goals" | "envelopes";

type GoalTemplate = {
  title: string;
  amount: string;
  label: string;
};

const ADULT_GOAL_TEMPLATES: GoalTemplate[] = [
  { title: "Bayram parası", amount: "1000", label: "Bayram parası — 1.000 ₺" },
  { title: "Diş parası", amount: "500", label: "Diş parası — 500 ₺" },
  { title: "Yeni okul", amount: "2500", label: "Yeni okul — 2.500 ₺" },
  { title: "Doğum günü hediyesi", amount: "750", label: "Doğum günü hediyesi — 750 ₺" },
  { title: "Acil durum", amount: "5000", label: "Acil durum — 5.000 ₺" },
];

const KID_GOAL_TEMPLATES: GoalTemplate[] = [
  { title: "Kumbara", amount: "200", label: "Kumbara — 200 ₺" },
  { title: "Bayram param", amount: "300", label: "Bayram param — 300 ₺" },
  { title: "Oyuncak", amount: "500", label: "Oyuncak — 500 ₺" },
  { title: "Dondurma bütçem", amount: "100", label: "Dondurma bütçem — 100 ₺" },
];

const GOAL_MILESTONES = [
  { threshold: 25, message: "Güzel başlangıç! Hedefin %25'ine ulaştın." },
  { threshold: 50, message: "Yarısını geçtin. Hedefin %50'si tamam." },
  { threshold: 75, message: "Son düzlük. Hedefin %75'ine ulaştın." },
  { threshold: 100, message: "Hedef tamamlandı. Harika iş!" },
] as const;

function formatMoney(value: string | null): string {
  if (value === null) return "0,00 ₺";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return `${value} ₺`;
  return `${new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numeric)} ₺`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function numericAmount(value: string | null): number {
  if (value === null) return 0;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? Math.max(0, numeric) : 0;
}

function barWidth(value: number, max: number): string {
  if (max <= 0 || value <= 0) return "0%";
  return `${Math.max(6, Math.min(100, (value / max) * 100))}%`;
}

function defaultTargetDate(): string {
  const value = new Date();
  value.setMonth(value.getMonth() + 12);
  return value.toISOString().slice(0, 10);
}

function dateAfterMonths(monthCount: number): string {
  const value = new Date();
  value.setMonth(value.getMonth() + monthCount);
  return value.toISOString().slice(0, 10);
}

function clampedProgress(value: string | null | undefined): number {
  const numeric = Number(value ?? "0");
  if (!Number.isFinite(numeric)) return 0;
  return Math.max(0, Math.min(100, numeric));
}

function statusLabel(status: SavingGoalProgress["status_label"]): string {
  if (status === "on_track") return "İyi gidiyor";
  if (status === "at_risk") return "Riskte";
  if (status === "over_limit") return "Limit aşıldı";
  return "Tamamlandı";
}

function goalHref(goalId: string): string {
  return `/goals?hedef=${encodeURIComponent(goalId)}`;
}

function goalIdFromLocation(): string | null {
  return new URL(window.location.href).searchParams.get("hedef");
}

function surfaceFromLocation(): GoalSurface {
  const url = new URL(window.location.href);
  return url.searchParams.has("zarf") || url.searchParams.get("sekme") === "zarflar"
    ? "envelopes"
    : "goals";
}

function surfaceHref(surface: GoalSurface): string {
  return surface === "goals" ? "/goals" : "/goals?sekme=zarflar";
}

function clearLegacyHashNavigation() {
  const url = new URL(window.location.href);
  if (url.hash !== "#zarflar" && url.hash !== "#hedefler") return;
  if (url.hash === "#zarflar" && !url.searchParams.has("zarf")) {
    url.searchParams.set("sekme", "zarflar");
  }
  url.hash = "";
  window.history.replaceState(null, "", `${url.pathname}${url.search}`);
  window.scrollTo({ top: 0, behavior: "auto" });
}

function goalTypeLabel(goalType: GoalMode): string {
  return goalType === "accumulation" ? "Birikim" : "Tasarruf";
}

function goalTypeDescription(goalType: GoalMode): string {
  return goalType === "accumulation"
    ? "Bir tutara ulaşmak için para ayırma"
    : "Bir gider kategorisini kontrollü azaltma";
}

function goalTone(goalType: GoalMode) {
  if (goalType === "accumulation") {
    return {
      badge: "border-primary/40 bg-primary/10 text-primary",
      button: "bg-primary text-primary-foreground hover:bg-primary/90",
      focus: "focus-visible:ring-primary/50",
      panel: "border-primary/30 bg-primary/10",
      progress: "bg-primary",
      row: "hover:border-primary/50 hover:bg-primary/5",
      selectedRow: "border-primary/70 bg-primary/10 ring-2 ring-primary/20",
      text: "text-primary",
    };
  }
  return {
    badge: "border-accent/60 bg-accent/25 text-accent-foreground",
    button: "bg-accent text-accent-foreground hover:bg-accent/90",
    focus: "focus-visible:ring-accent/60",
    panel: "border-accent/50 bg-accent/20",
    progress: "bg-accent",
    row: "hover:border-accent/60 hover:bg-accent/10",
    selectedRow: "border-accent/75 bg-accent/20 ring-2 ring-accent/25",
    text: "text-accent-foreground",
  };
}

function goalStatusText(goal: SavingGoal, progress?: SavingGoalProgress): string {
  if (goal.status === "paused") return "Duraklatıldı";
  if (goal.status === "completed") return "Tamamlandı";
  return progress ? statusLabel(progress.status_label) : "Yükleniyor";
}

function friendlyError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

function RelatedSpendingList({
  transactions,
  categoryId,
  userId,
  categoryName,
}: {
  transactions: Transaction[];
  categoryId: string;
  userId: string;
  categoryName: string;
}) {
  const related = transactions
    .filter(
      (transaction) =>
        transaction.type === "expense" &&
        transaction.user_id === userId &&
        transaction.category_id === categoryId,
    )
    .slice(0, 8);

  return (
    <div className="mt-6 rounded-[1.4rem] border border-border/70 bg-muted/35 p-4">
      <div className="flex items-center gap-2">
        <ListChecks className="h-4 w-4 text-primary" />
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-muted-foreground">
          {categoryName} hedefiyle ilgili son hareketler
        </p>
      </div>
      {related.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">
          Bu hedefe ait yakın zamanda kayıtlı bir harcama bulunamadı.
        </p>
      ) : (
        <ul className="mt-3 divide-y divide-border/60">
          {related.map((transaction) => (
            <li
              key={transaction.id}
              className="flex items-center justify-between gap-3 py-2 text-sm"
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-foreground">
                  {transaction.merchant?.trim() || transaction.description?.trim() || "Harcama"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {formatDate(transaction.occurred_at)}
                </p>
              </div>
              <span className="font-display text-base font-bold tabular-nums">
                {formatMoney(transaction.amount)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function SavingGoalsClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isKid } = useKidMode();
  const [categories, setCategories] = useState<Category[]>([]);
  const [goals, setGoals] = useState<SavingGoal[]>([]);
  const [progressByGoalId, setProgressByGoalId] = useState<Record<string, SavingGoalProgress>>({});
  const [contributionByGoalId, setContributionByGoalId] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<GoalMode>("accumulation");
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [targetReductionPercent, setTargetReductionPercent] = useState("15");
  const [accumulationTitle, setAccumulationTitle] = useState("Tatil birikimi");
  const [targetAmount, setTargetAmount] = useState("20000");
  const [currentAmount, setCurrentAmount] = useState("0");
  const [targetDate, setTargetDate] = useState(defaultTargetDate);
  const [selectedGoalId, setSelectedGoalId] = useState<string | null>(null);
  const [activeSurface, setActiveSurface] = useState<GoalSurface>("goals");
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [actionGoalId, setActionGoalId] = useState<string | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const milestoneProgressRef = useRef<Record<string, number>>({});
  const milestoneReadyRef = useRef(false);

  async function loadGoals() {
    const [categoryRows, goalRows, transactionRows] = await Promise.all([
      api<Category[]>("/api/categories", { silent: true }),
      api<SavingGoal[]>("/api/saving-goals", { silent: true }),
      api<Transaction[]>("/api/transactions?limit=100", { silent: true }),
    ]);
    setCategories(categoryRows);
    setGoals(goalRows);
    setTransactions(transactionRows);
    const requestedGoalId = goalIdFromLocation();
    if (goalRows.length === 0) {
      setSelectedGoalId(null);
    } else if (requestedGoalId && goalRows.some((goal) => goal.id === requestedGoalId)) {
      setSelectedGoalId(requestedGoalId);
    } else if (!selectedGoalId || !goalRows.some((goal) => goal.id === selectedGoalId)) {
      setSelectedGoalId(goalRows[0]?.id ?? null);
    }
    if (!selectedCategoryId && categoryRows[0]) setSelectedCategoryId(categoryRows[0].id);

    const progressRows = await Promise.all(
      goalRows.map((goal) =>
        api<SavingGoalProgress>(`/api/saving-goals/${goal.id}/progress`, { silent: true }),
      ),
    );
    setProgressByGoalId(
      Object.fromEntries(progressRows.map((progress) => [progress.goal.id, progress])),
    );
  }

  useEffect(() => {
    clearLegacyHashNavigation();
    let ignore = false;
    async function load() {
      try {
        await loadGoals();
        if (!ignore) setError(null);
      } catch (err) {
        if (!ignore) setError(friendlyError(err, "Akıllı hedefler yüklenemedi."));
      }
    }
    void load();
    return () => {
      ignore = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- initial load only; form state should not refetch.
  }, []);

  // Use the serialized query string as the dependency so this effect fires on
  // every query change — `useSearchParams()` itself can hand back a stable
  // ReadonlyURLSearchParams reference in some Next.js navigation paths
  // (notably when only the query changes and pathname stays put, e.g. the
  // sidebar Zarflar link going from /goals to /goals?sekme=zarflar). Compare
  // by string content to keep the surface in sync with the URL deterministically.
  const searchParamsKey = searchParams.toString();
  useEffect(
    () => {
      const requestedGoalId = searchParams.get("hedef");
      const isEnvelopeRoute = searchParams.has("zarf") || searchParams.get("sekme") === "zarflar";
      setActiveSurface(isEnvelopeRoute ? "envelopes" : "goals");
      if (requestedGoalId && goals.some((goal) => goal.id === requestedGoalId)) {
        setSelectedGoalId(requestedGoalId);
      } else if (requestedGoalId === null && !isEnvelopeRoute) {
        setSelectedGoalId((current) => current ?? goals[0]?.id ?? null);
      }
    },
    // searchParams itself is intentionally not a dep — `useSearchParams()` can
    // return a stable reference across query-only navigations. Trigger on the
    // serialized content of the query string instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [goals, searchParamsKey],
  );

  useEffect(() => {
    const requestedGoalId = goalIdFromLocation();
    if (requestedGoalId && goals.some((goal) => goal.id === requestedGoalId)) {
      setSelectedGoalId(requestedGoalId);
    }
    setActiveSurface(surfaceFromLocation());
  }, [goals]);

  useEffect(() => {
    function handleLocationChange() {
      const nextGoalId = goalIdFromLocation();
      setSelectedGoalId(nextGoalId);
      setActiveSurface(surfaceFromLocation());
    }

    window.addEventListener("popstate", handleLocationChange);
    window.addEventListener("hashchange", handleLocationChange);
    return () => {
      window.removeEventListener("popstate", handleLocationChange);
      window.removeEventListener("hashchange", handleLocationChange);
    };
  }, []);

  useEffect(() => {
    if (goals.length === 0) {
      milestoneProgressRef.current = {};
      milestoneReadyRef.current = false;
      return;
    }

    const allProgressLoaded = goals.every((goal) => progressByGoalId[goal.id] !== undefined);
    if (!allProgressLoaded) return;

    const nextProgress: Record<string, number> = {};
    for (const goal of goals) {
      const progress = clampedProgress(progressByGoalId[goal.id]?.progress_percent);
      nextProgress[goal.id] = progress;
      const previous = milestoneProgressRef.current[goal.id];
      if (!milestoneReadyRef.current || previous === undefined) continue;
      const crossed = [...GOAL_MILESTONES]
        .reverse()
        .find((milestone) => previous < milestone.threshold && progress >= milestone.threshold);
      if (crossed) toast.success(`${goal.title}: ${crossed.message}`);
    }

    milestoneProgressRef.current = nextProgress;
    milestoneReadyRef.current = true;
  }, [goals, progressByGoalId]);

  function applyGoalTemplate(template: GoalTemplate) {
    setAccumulationTitle(template.title);
    setTargetAmount(template.amount);
    setCurrentAmount("0");
    setTargetDate(dateAfterMonths(6));
    setMode("accumulation");
  }

  function handleCreateGoal() {
    setIsSaving(true);
    setError(null);
    void (async () => {
      try {
        if (mode === "accumulation") {
          if (!targetDate) {
            setError("Birikim hedefi için hedef tarihi seçer misin?");
            return;
          }
          const normalizedTarget = normalizeAmountInput(targetAmount);
          const normalizedCurrent = normalizeAmountInput(currentAmount || "0");
          if (!isValidAmount(normalizedTarget) || !isValidAmount(normalizedCurrent)) {
            setError("Birikim tutarını 1250,50 biçiminde girer misin?");
            return;
          }
          await api<SavingGoal>("/api/saving-goals", {
            method: "POST",
            body: {
              goal_type: "accumulation",
              title: accumulationTitle,
              target_amount: normalizedTarget,
              current_amount: normalizedCurrent,
              target_date: new Date(`${targetDate}T12:00:00+03:00`).toISOString(),
            },
          });
          toast.success("Birikim hedefi oluşturuldu.");
        } else {
          await api<SavingGoal>("/api/saving-goals", {
            method: "POST",
            body: {
              goal_type: "expense_reduction",
              category_id: selectedCategoryId,
              target_reduction_percent: targetReductionPercent,
            },
          });
          toast.success("Tasarruf hedefi oluşturuldu.");
        }
        await loadGoals();
      } catch (err) {
        setError(friendlyError(err, "Hedef oluşturulamadı."));
      } finally {
        setIsSaving(false);
      }
    })();
  }

  function handleGoalSelect(event: MouseEvent<HTMLAnchorElement>, goalId: string) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
      return;
    }

    event.preventDefault();
    setActiveSurface("goals");
    setSelectedGoalId(goalId);
    router.push(goalHref(goalId));
  }

  function handleSurfaceSelect(event: MouseEvent<HTMLAnchorElement>, surface: GoalSurface) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
      return;
    }

    event.preventDefault();
    setActiveSurface(surface);
    const nextHref =
      surface === "goals" && selectedGoalId ? goalHref(selectedGoalId) : surfaceHref(surface);
    router.push(nextHref);
  }

  async function patchGoal(
    goal: SavingGoal,
    payload: SavingGoalUpdateInput,
    successMessage: string,
  ): Promise<boolean> {
    setActionGoalId(goal.id);
    setError(null);
    try {
      await api<SavingGoal>(`/api/saving-goals/${goal.id}`, {
        method: "PATCH",
        body: payload,
      });
      toast.success(successMessage);
      await loadGoals();
      return true;
    } catch (err) {
      setError(friendlyError(err, "Hedef güncellenemedi."));
      return false;
    } finally {
      setActionGoalId(null);
    }
  }

  function handleAddContribution(goal: SavingGoal) {
    const normalized = normalizeAmountInput(contributionByGoalId[goal.id] ?? "");
    if (!isValidAmount(normalized)) {
      setError("Katkı tutarını 1250,50 biçiminde girer misin?");
      return;
    }
    void (async () => {
      const updated = await patchGoal(
        goal,
        { contribution_amount: normalized },
        "Katkı hedefe eklendi.",
      );
      if (updated) setContributionByGoalId((current) => ({ ...current, [goal.id]: "" }));
    })();
  }

  function handleDeleteGoal(goal: SavingGoal) {
    const confirmed = window.confirm("Bu hedefi silmek istediğine emin misin?");
    if (!confirmed) return;
    setActionGoalId(goal.id);
    setError(null);
    void (async () => {
      try {
        await api<void>(`/api/saving-goals/${goal.id}`, { method: "DELETE" });
        toast.success("Hedef silindi.");
        await loadGoals();
      } catch (err) {
        setError(friendlyError(err, "Hedef silinemedi."));
      } finally {
        setActionGoalId(null);
      }
    })();
  }

  function askCoachForPlan(goal: SavingGoal) {
    const goalType = goal.goal_type === "accumulation" ? "birikim" : "tasarruf";
    rememberPendingChatMessage({
      source: "dashboard",
      title: `${goal.title} için plan`,
      startNew: true,
      message: `${goal.title} adlı ${goalType} hedefim için bütçe koçluğu planı çıkar. Yatırım tavsiyesi verme; harcama alışkanlıkları, haftalık takip ve güvenli katkı önerileriyle açıkla.`,
    });
    router.push("/chat");
  }

  const accumulationGoals = goals.filter((goal) => goal.goal_type === "accumulation");
  const reductionGoals = goals.filter((goal) => goal.goal_type === "expense_reduction");
  const orderedGoals = [...accumulationGoals, ...reductionGoals];
  const selectedGoal = orderedGoals.find((goal) => goal.id === selectedGoalId) ?? orderedGoals[0];
  const selectedProgress = selectedGoal ? progressByGoalId[selectedGoal.id] : null;
  const selectedIsAccumulation = selectedGoal?.goal_type === "accumulation";
  const selectedProgressWidth = selectedProgress
    ? Math.max(0, Math.min(100, Number(selectedProgress.progress_percent)))
    : 0;
  const selectedActualValue = selectedIsAccumulation
    ? numericAmount(selectedGoal?.current_amount ?? null)
    : numericAmount(selectedProgress?.actual_spending ?? null);
  const selectedTargetValue = selectedIsAccumulation
    ? numericAmount(selectedGoal?.target_amount ?? null)
    : numericAmount(selectedGoal?.target_spending_amount ?? null);
  const selectedChartMax = Math.max(selectedActualValue, selectedTargetValue, 1);
  const selectedTone = selectedGoal ? goalTone(selectedGoal.goal_type) : null;
  const goalGroups = [
    {
      key: "accumulation",
      title: "Birikim hedefleri",
      helper: "Tatil, okul masrafı veya acil durum gibi tutara bağlı planlar.",
      goals: accumulationGoals,
    },
    {
      key: "expense_reduction",
      title: "Tasarruf hedefleri",
      helper: "Market, eğlence veya fatura gibi giderleri kontrollü azaltma planları.",
      goals: reductionGoals,
    },
  ] as const;
  const goalTemplates = isKid ? KID_GOAL_TEMPLATES : ADULT_GOAL_TEMPLATES;

  return (
    <main className="space-y-4 p-4 sm:p-6 lg:p-8">
      <nav
        aria-label="Hedef ve zarf seçimi"
        className="grid gap-2 rounded-[1.6rem] border border-border/80 bg-card/80 p-2 shadow-sm sm:grid-cols-2"
      >
        {(
          [
            ["goals", "Hedefler", "Birikim ve tasarruf planları"],
            ["envelopes", "Zarflar", "Aylık harcama sınırları"],
          ] as const
        ).map(([surface, label, helper]) => {
          const isActive = activeSurface === surface;
          return (
            <Link
              key={surface}
              href={surfaceHref(surface)}
              aria-current={isActive ? "page" : undefined}
              onClick={(event) => handleSurfaceSelect(event, surface)}
              className={cn(
                "rounded-[1.25rem] px-4 py-3 transition-all duration-200 ease-quint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                isActive
                  ? "bg-primary text-primary-foreground shadow-lg shadow-primary/10"
                  : "text-muted-foreground hover:bg-muted/70 hover:text-foreground",
              )}
            >
              <span className="font-display text-lg font-black">{label}</span>
              <span className="mt-1 block text-xs font-medium opacity-80">{helper}</span>
            </Link>
          );
        })}
      </nav>

      {activeSurface === "goals" ? (
        <>
          <section className="receipt-tape hard-shadow relative overflow-hidden rounded-[2rem] border border-border/80 bg-card p-5 sm:p-6">
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start">
              <div className="max-w-2xl space-y-3">
                <span className="stamp-label bg-primary/10 text-primary">Akıllı hedefler</span>
                <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
                  Birikimi ve tasarrufu aynı defterde izle
                </h1>
                <p className="text-sm leading-6 text-muted-foreground sm:text-base">
                  Birikim hedefi belirli bir tutara ulaşmayı, tasarruf hedefi ise bir gider
                  kategorisini kontrollü azaltmayı takip eder. İkisi de yatırım tavsiyesi değil,
                  bütçe koçluğudur.
                </p>
                <div className="grid gap-2 sm:grid-cols-2">
                  {(["accumulation", "expense_reduction"] as const).map((nextMode) => {
                    const tone = goalTone(nextMode);
                    const isActive = mode === nextMode;
                    const Icon = nextMode === "accumulation" ? PiggyBank : Target;
                    return (
                      <button
                        key={nextMode}
                        type="button"
                        aria-pressed={isActive}
                        onClick={() => setMode(nextMode)}
                        className={cn(
                          "rounded-[1.35rem] border p-3 text-left transition-all duration-200 ease-quint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
                          tone.focus,
                          isActive
                            ? tone.panel
                            : "border-border/70 bg-background/70 hover:bg-background",
                        )}
                      >
                        <span
                          className={cn(
                            "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-black",
                            tone.badge,
                          )}
                        >
                          <Icon className="h-4 w-4" />
                          {goalTypeLabel(nextMode)}
                        </span>
                        <span className="mt-2 block text-sm font-bold text-foreground">
                          {goalTypeDescription(nextMode)}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div
                className={cn(
                  "grid gap-3 rounded-[1.5rem] border border-dashed p-4 lg:min-h-[13.25rem] lg:content-start",
                  goalTone(mode).panel,
                )}
              >
                {mode === "accumulation" ? (
                  <div className="space-y-3">
                    <div className="grid gap-3 sm:grid-cols-2">
                      <label className="grid gap-1.5">
                        <span className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                          Hedef adı
                        </span>
                        <Input
                          value={accumulationTitle}
                          onChange={(event) => setAccumulationTitle(event.target.value)}
                        />
                      </label>
                      <label className="grid gap-1.5">
                        <span className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                          Hedef tarih
                        </span>
                        <Input
                          type="date"
                          value={targetDate}
                          onChange={(event) => setTargetDate(event.target.value)}
                        />
                      </label>
                      <label className="grid gap-1.5">
                        <span className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                          Hedef tutar
                        </span>
                        <Input
                          inputMode="decimal"
                          value={targetAmount}
                          onChange={(event) => setTargetAmount(event.target.value)}
                        />
                      </label>
                      <label className="grid gap-1.5">
                        <span className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                          Şu an ayrılan tutar
                        </span>
                        <Input
                          inputMode="decimal"
                          value={currentAmount}
                          onChange={(event) => setCurrentAmount(event.target.value)}
                        />
                      </label>
                    </div>
                    <div className="flex min-w-0 items-center gap-2 overflow-x-auto pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                      <span className="shrink-0 text-[0.65rem] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                        Hızlı:
                      </span>
                      {goalTemplates.map((template) => (
                        <button
                          key={template.label}
                          type="button"
                          onClick={() => applyGoalTemplate(template)}
                          className="shrink-0 rounded-full border border-border/70 bg-card/75 px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:border-primary/45 hover:bg-primary/10"
                        >
                          {template.label}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="grid gap-3 sm:grid-cols-2">
                    <label className="grid gap-1.5">
                      <span className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                        Kategori
                      </span>
                      <select
                        className="h-11 rounded-xl border border-input bg-background px-3 text-sm font-medium"
                        value={selectedCategoryId}
                        onChange={(event) => setSelectedCategoryId(event.target.value)}
                      >
                        {categories.map((category) => (
                          <option key={category.id} value={category.id}>
                            {category.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="grid gap-1.5">
                      <span className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                        Azaltma hedefi (%)
                      </span>
                      <Input
                        inputMode="decimal"
                        value={targetReductionPercent}
                        onChange={(event) => setTargetReductionPercent(event.target.value)}
                      />
                    </label>
                  </div>
                )}
                <Button
                  disabled={(mode === "expense_reduction" && !selectedCategoryId) || isSaving}
                  onClick={handleCreateGoal}
                  className={cn(mode === "expense_reduction" ? goalTone(mode).button : "")}
                >
                  {mode === "accumulation" ? (
                    <PiggyBank className="h-4 w-4" />
                  ) : (
                    <Target className="h-4 w-4" />
                  )}
                  Hedef oluştur
                </Button>
              </div>
            </div>
          </section>

          {error ? (
            <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-4 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          <section
            id="hedefler"
            className="grid scroll-mt-24 gap-5 2xl:grid-cols-[minmax(21rem,0.72fr)_minmax(0,1.28fr)]"
          >
            <div className="ledger-sheet p-4 sm:p-5">
              <div className="relative z-10 space-y-4">
                <div>
                  <p className="eyebrow">Hedefler</p>
                  <h2 className="mt-1 font-display text-2xl font-black leading-none">
                    Birikim ve tasarruf
                  </h2>
                </div>

                {goals.length === 0 ? (
                  <p className="rounded-[1.25rem] border border-border/70 bg-background/70 p-3 text-sm font-bold text-muted-foreground">
                    Henüz hedef yok. Birikim tutarı veya gider azaltma hedefiyle başlayabilirsin.
                  </p>
                ) : (
                  <div className="grid gap-4">
                    {goalGroups.map((group) => (
                      <section key={group.key} className="space-y-2.5">
                        <div className="flex items-end justify-between gap-3">
                          <div>
                            <h3 className="font-display text-lg font-black leading-tight">
                              {group.title}
                            </h3>
                            <p className="mt-0.5 text-xs leading-5 text-muted-foreground">
                              {group.helper}
                            </p>
                          </div>
                          <span className="rounded-full border border-border/70 bg-background/70 px-2.5 py-1 text-[0.68rem] font-black text-muted-foreground">
                            {group.goals.length}
                          </span>
                        </div>
                        <div className="grid gap-2.5">
                          {group.goals.map((goal) => {
                            const progress = progressByGoalId[goal.id];
                            const progressWidth = progress
                              ? Math.max(0, Math.min(100, Number(progress.progress_percent)))
                              : 0;
                            const isAccumulation = goal.goal_type === "accumulation";
                            const isSelected = goal.id === selectedGoal?.id;
                            const tone = goalTone(goal.goal_type);
                            const Icon = isAccumulation ? PiggyBank : Target;
                            return (
                              <Link
                                key={goal.id}
                                href={goalHref(goal.id)}
                                aria-current={isSelected ? "page" : undefined}
                                onClick={(event) => handleGoalSelect(event, goal.id)}
                                className={cn(
                                  "block rounded-[1.35rem] border p-3 transition-all duration-200 ease-quint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2",
                                  tone.focus,
                                  isSelected
                                    ? tone.selectedRow
                                    : "border-border/70 bg-background/70",
                                  tone.row,
                                )}
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <div className="min-w-0">
                                    <span
                                      className={cn(
                                        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.68rem] font-black",
                                        tone.badge,
                                      )}
                                    >
                                      <Icon className="h-3.5 w-3.5" />
                                      {goalTypeLabel(goal.goal_type)}
                                    </span>
                                    <h2 className="mt-2 truncate font-display text-lg font-black">
                                      {goal.title}
                                    </h2>
                                    <p className="mt-1 text-xs font-bold text-muted-foreground">
                                      {isAccumulation ? "Hedef tutar" : goal.category_name}
                                    </p>
                                  </div>
                                  <span className="rounded-full bg-secondary px-2.5 py-1 text-[0.68rem] font-black text-secondary-foreground">
                                    {goalStatusText(goal, progress)}
                                  </span>
                                </div>

                                {progress ? (
                                  <div className="mt-3 space-y-2">
                                    <div className="h-2 overflow-hidden rounded-full bg-muted">
                                      <div
                                        className={cn(
                                          "h-full rounded-full transition-all",
                                          tone.progress,
                                        )}
                                        style={{ width: `${progressWidth}%` }}
                                      />
                                    </div>
                                    <div className="flex items-end justify-between gap-3 text-xs font-bold text-muted-foreground">
                                      <span>{isAccumulation ? "Kalan" : "Kalan limit"}</span>
                                      <span className="tabular-nums text-foreground">
                                        {formatMoney(
                                          isAccumulation
                                            ? progress.remaining_amount
                                            : progress.remaining_limit,
                                        )}
                                      </span>
                                    </div>
                                  </div>
                                ) : null}

                                <p
                                  className={cn(
                                    "mt-3 text-xs font-black uppercase tracking-[0.16em]",
                                    tone.text,
                                  )}
                                >
                                  Detayı aç
                                </p>
                              </Link>
                            );
                          })}
                        </div>
                      </section>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {selectedGoal && selectedTone ? (
              <section
                key={selectedGoal.id}
                className={cn(
                  "detail-swap rounded-[1.8rem] border p-5 shadow-sm sm:p-6",
                  selectedTone.panel,
                )}
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <span
                      className={cn(
                        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-black",
                        selectedTone.badge,
                      )}
                    >
                      {selectedIsAccumulation ? (
                        <PiggyBank className="h-4 w-4" />
                      ) : (
                        <Target className="h-4 w-4" />
                      )}
                      {goalTypeLabel(selectedGoal.goal_type)} hedefi
                    </span>
                    <h2 className="mt-1 font-display text-3xl font-bold">{selectedGoal.title}</h2>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {selectedIsAccumulation
                        ? "Birikim ilerlemesi, kalan tutar ve aylık katkı planı."
                        : `${selectedGoal.category_name} harcaması için hedef limit ve taktikler.`}
                    </p>
                  </div>
                  <span className="w-fit rounded-full bg-secondary px-3 py-1 text-xs font-bold text-secondary-foreground">
                    {goalStatusText(selectedGoal, selectedProgress ?? undefined)}
                  </span>
                </div>

                <div
                  className={cn(
                    "mt-5 grid gap-3 rounded-[1.4rem] border border-dashed p-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end",
                    selectedTone.panel,
                  )}
                >
                  <div className="space-y-3">
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-muted-foreground">
                      Hedef aksiyonları
                    </p>
                    {selectedIsAccumulation && selectedGoal.status === "active" ? (
                      <div className="grid gap-2 sm:grid-cols-[minmax(0,14rem)_auto]">
                        <Input
                          inputMode="decimal"
                          placeholder="Katkı tutarı"
                          value={contributionByGoalId[selectedGoal.id] ?? ""}
                          onChange={(event) =>
                            setContributionByGoalId((current) => ({
                              ...current,
                              [selectedGoal.id]: event.target.value,
                            }))
                          }
                        />
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={actionGoalId === selectedGoal.id}
                          onClick={() => handleAddContribution(selectedGoal)}
                        >
                          <Plus className="h-4 w-4" />
                          Katkı ekle
                        </Button>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">
                        {selectedIsAccumulation
                          ? "Bu hedef aktif değil; yeni katkı eklenmiyor."
                          : "Tasarruf hedeflerinde ilerleme ilgili kategori harcamalarından hesaplanır."}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    {selectedGoal.status === "paused" ? (
                      <Button
                        type="button"
                        variant="outline"
                        disabled={actionGoalId === selectedGoal.id}
                        onClick={() =>
                          void patchGoal(selectedGoal, { status: "active" }, "Hedef yeniden aktif.")
                        }
                      >
                        <PlayCircle className="h-4 w-4" />
                        Sürdür
                      </Button>
                    ) : (
                      <Button
                        type="button"
                        variant="outline"
                        disabled={
                          actionGoalId === selectedGoal.id || selectedGoal.status !== "active"
                        }
                        onClick={() =>
                          void patchGoal(selectedGoal, { status: "paused" }, "Hedef duraklatıldı.")
                        }
                      >
                        <PauseCircle className="h-4 w-4" />
                        Duraklat
                      </Button>
                    )}
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={
                        actionGoalId === selectedGoal.id || selectedGoal.status === "completed"
                      }
                      onClick={() =>
                        void patchGoal(selectedGoal, { status: "completed" }, "Hedef tamamlandı.")
                      }
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      Tamamlandı
                    </Button>
                    <Button type="button" onClick={() => askCoachForPlan(selectedGoal)}>
                      <MessageCircle className="h-4 w-4" />
                      Koçtan plan iste
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      className="text-destructive hover:text-destructive"
                      disabled={actionGoalId === selectedGoal.id}
                      onClick={() => handleDeleteGoal(selectedGoal)}
                    >
                      <Trash2 className="h-4 w-4" />
                      Sil
                    </Button>
                  </div>
                </div>

                {selectedProgress ? (
                  <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
                    <div className="space-y-5">
                      <div className="h-4 overflow-hidden rounded-full bg-muted">
                        <div
                          className={cn(
                            "h-full rounded-full transition-all",
                            selectedTone.progress,
                          )}
                          style={{ width: `${selectedProgressWidth}%` }}
                        />
                      </div>
                      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <div className="rounded-2xl bg-muted/55 p-3">
                          <p className="text-xs text-muted-foreground">
                            {selectedIsAccumulation ? "Şu an" : "Şu ana kadar"}
                          </p>
                          <p className="font-display text-xl font-bold">
                            {formatMoney(
                              selectedIsAccumulation
                                ? selectedGoal.current_amount
                                : selectedProgress.actual_spending,
                            )}
                          </p>
                        </div>
                        <div className={cn("rounded-2xl p-3", selectedTone.panel)}>
                          <p className="text-xs text-muted-foreground">
                            {selectedIsAccumulation ? "Hedef tutar" : "Hedef limit"}
                          </p>
                          <p className={cn("font-display text-xl font-bold", selectedTone.text)}>
                            {formatMoney(
                              selectedIsAccumulation
                                ? selectedGoal.target_amount
                                : selectedGoal.target_spending_amount,
                            )}
                          </p>
                        </div>
                        <div className="rounded-2xl bg-background/65 p-3">
                          <p className="text-xs text-muted-foreground">
                            {selectedIsAccumulation ? "Kalan" : "Kalan limit"}
                          </p>
                          <p className="font-display text-xl font-bold text-foreground">
                            {formatMoney(
                              selectedIsAccumulation
                                ? selectedProgress.remaining_amount
                                : selectedProgress.remaining_limit,
                            )}
                          </p>
                        </div>
                        <div className="rounded-2xl bg-muted/55 p-3">
                          <p className="text-xs text-muted-foreground">
                            {selectedIsAccumulation ? "Hedef tarih" : "Dönem"}
                          </p>
                          <p className="font-display text-lg font-bold">
                            {selectedIsAccumulation
                              ? formatDate(selectedGoal.end_date)
                              : `${formatDate(selectedGoal.start_date)}-${formatDate(selectedGoal.end_date)}`}
                          </p>
                        </div>
                      </div>

                      <div className="rounded-[1.4rem] border border-border/70 bg-background/55 p-4">
                        <p className="text-xs font-bold uppercase tracking-[0.16em] text-muted-foreground">
                          İlerleme grafiği
                        </p>
                        <div className="mt-4 space-y-3">
                          <div>
                            <div className="mb-1 flex justify-between text-xs font-medium">
                              <span>{selectedIsAccumulation ? "Şu an" : "Bu ay harcama"}</span>
                              <span>{formatMoney(String(selectedActualValue))}</span>
                            </div>
                            <div className="h-3 overflow-hidden rounded-full bg-background">
                              <div
                                className={cn("h-full rounded-full", selectedTone.progress)}
                                style={{ width: barWidth(selectedActualValue, selectedChartMax) }}
                              />
                            </div>
                          </div>
                          <div>
                            <div className="mb-1 flex justify-between text-xs font-medium">
                              <span>{selectedIsAccumulation ? "Hedef" : "Hedef limit"}</span>
                              <span>{formatMoney(String(selectedTargetValue))}</span>
                            </div>
                            <div className="h-3 overflow-hidden rounded-full bg-background">
                              <div
                                className="h-full rounded-full bg-muted-foreground/40"
                                style={{ width: barWidth(selectedTargetValue, selectedChartMax) }}
                              />
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    <aside
                      className={cn(
                        "rounded-[1.4rem] border border-dashed p-4",
                        selectedTone.panel,
                      )}
                    >
                      <p className="text-xs font-bold uppercase tracking-[0.16em] text-muted-foreground">
                        AI taktikleri
                      </p>
                      <ul className="mt-3 space-y-2 text-sm text-foreground/85">
                        {selectedProgress.tactics.map((tactic) => (
                          <li key={tactic} className="rounded-xl bg-background/75 px-3 py-2">
                            {tactic}
                          </li>
                        ))}
                      </ul>
                    </aside>
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-muted-foreground">Hedef detayı yükleniyor.</p>
                )}

                {selectedGoal.goal_type === "expense_reduction" && selectedGoal.category_id ? (
                  <RelatedSpendingList
                    transactions={transactions}
                    categoryId={selectedGoal.category_id}
                    userId={selectedGoal.user_id}
                    categoryName={selectedGoal.category_name}
                  />
                ) : null}
              </section>
            ) : null}
          </section>
        </>
      ) : null}

      {activeSurface === "envelopes" ? <EnvelopeBudgetClient embedded /> : null}
    </main>
  );
}
