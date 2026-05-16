"use client";

import {
  CheckCircle2,
  MessageCircle,
  PauseCircle,
  PlayCircle,
  PiggyBank,
  Plus,
  Target,
  Trash2,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";
import { rememberPendingChatMessage } from "@/lib/chat-session";
import { isValidAmount, normalizeAmountInput } from "@/lib/money-input";
import type { Category, SavingGoal, SavingGoalProgress, SavingGoalUpdateInput } from "@/lib/types";
import { cn } from "@/lib/utils";

type GoalMode = "accumulation" | "expense_reduction";

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

function statusLabel(status: SavingGoalProgress["status_label"]): string {
  if (status === "on_track") return "İyi gidiyor";
  if (status === "at_risk") return "Riskte";
  if (status === "over_limit") return "Limit aşıldı";
  return "Tamamlandı";
}

function goalStatusText(goal: SavingGoal, progress?: SavingGoalProgress): string {
  if (goal.status === "paused") return "Duraklatıldı";
  if (goal.status === "completed") return "Tamamlandı";
  return progress ? statusLabel(progress.status_label) : "Yükleniyor";
}

function friendlyError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

export function SavingGoalsClient() {
  const router = useRouter();
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
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [actionGoalId, setActionGoalId] = useState<string | null>(null);

  async function loadGoals() {
    const [categoryRows, goalRows] = await Promise.all([
      api<Category[]>("/api/categories", { silent: true }),
      api<SavingGoal[]>("/api/saving-goals", { silent: true }),
    ]);
    setCategories(categoryRows);
    setGoals(goalRows);
    if (goalRows.length === 0) {
      setSelectedGoalId(null);
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

  function selectGoal(goalId: string) {
    setSelectedGoalId(goalId);
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

  return (
    <main className="space-y-5 p-4 sm:p-6 lg:p-8">
      <section className="receipt-tape hard-shadow relative overflow-hidden rounded-[2rem] border border-border/80 bg-card p-5 sm:p-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-start">
          <div className="max-w-2xl space-y-3">
            <span className="stamp-label bg-primary/10 text-primary">Akıllı hedefler</span>
            <h1 className="font-display text-2xl font-bold tracking-tight sm:text-3xl">
              Birikimi ve tasarrufu aynı defterde izle
            </h1>
            <p className="text-sm leading-6 text-muted-foreground sm:text-base">
              Birikim hedefi belirli bir tutara ulaşmayı, tasarruf hedefi ise bir gider kategorisini
              kontrollü azaltmayı takip eder. İkisi de yatırım tavsiyesi değil, bütçe koçluğudur.
            </p>
            <div className="flex flex-wrap gap-2">
              {(["accumulation", "expense_reduction"] as const).map((nextMode) => (
                <Button
                  key={nextMode}
                  type="button"
                  variant={mode === nextMode ? "default" : "outline"}
                  onClick={() => setMode(nextMode)}
                >
                  {nextMode === "accumulation" ? (
                    <PiggyBank className="h-4 w-4" />
                  ) : (
                    <Target className="h-4 w-4" />
                  )}
                  {nextMode === "accumulation" ? "Birikim hedefi" : "Tasarruf hedefi"}
                </Button>
              ))}
            </div>
          </div>

          <div className="grid gap-3 rounded-[1.5rem] border border-dashed border-primary/30 bg-primary/5 p-4">
            {mode === "accumulation" ? (
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

      <section className="grid gap-3 lg:grid-cols-2">
        {goals.length === 0 ? (
          <div className="ledger-card rounded-[1.5rem] border border-border/80 bg-card p-6 text-sm text-muted-foreground lg:col-span-2">
            Henüz hedef yok. Birikim tutarı veya gider azaltma hedefiyle başlayabilirsin.
          </div>
        ) : null}

        {orderedGoals.map((goal) => {
          const progress = progressByGoalId[goal.id];
          const progressWidth = progress
            ? Math.max(0, Math.min(100, Number(progress.progress_percent)))
            : 0;
          const isAccumulation = goal.goal_type === "accumulation";
          const isSelected = goal.id === selectedGoal?.id;
          return (
            <article
              key={goal.id}
              role="button"
              tabIndex={0}
              aria-pressed={isSelected}
              onClick={() => selectGoal(goal.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  selectGoal(goal.id);
                }
              }}
              className={cn(
                "ledger-card flex h-full cursor-pointer flex-col rounded-[1.5rem] border border-border/80 bg-card p-4 text-left transition-all hover:-translate-y-0.5 hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 sm:p-5",
                isAccumulation ? "bg-primary/5" : "",
                isSelected ? "border-primary/60 ring-2 ring-primary/20" : "",
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                    {isAccumulation ? "Birikim" : goal.category_name}
                  </p>
                  <h2 className="mt-1 font-display text-xl font-bold">{goal.title}</h2>
                </div>
                <span className="rounded-full bg-secondary px-3 py-1 text-xs font-bold text-secondary-foreground">
                  {goalStatusText(goal, progress)}
                </span>
              </div>

              <div className="mt-4 grid gap-2 sm:grid-cols-3">
                <div className="rounded-2xl bg-muted/60 p-3">
                  <p className="text-xs text-muted-foreground">
                    {isAccumulation ? "Şu an" : "Geçen dönem"}
                  </p>
                  <p className="font-display text-lg font-bold">
                    {formatMoney(isAccumulation ? goal.current_amount : goal.baseline_amount)}
                  </p>
                </div>
                <div className="rounded-2xl bg-primary/10 p-3">
                  <p className="text-xs text-muted-foreground">
                    {isAccumulation ? "Hedef tutar" : "Bu ay limit"}
                  </p>
                  <p className="font-display text-lg font-bold text-primary">
                    {formatMoney(isAccumulation ? goal.target_amount : goal.target_spending_amount)}
                  </p>
                </div>
                <div className="rounded-2xl bg-accent/10 p-3">
                  <p className="text-xs text-muted-foreground">
                    {isAccumulation ? "Aylık katkı" : "Beklenen tasarruf"}
                  </p>
                  <p className="font-display text-lg font-bold text-accent-foreground">
                    {formatMoney(
                      isAccumulation ? goal.monthly_contribution : goal.target_saving_amount,
                    )}
                  </p>
                </div>
              </div>

              {progress ? (
                <div className="mt-4 space-y-2">
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${progressWidth}%` }}
                    />
                  </div>
                  <p className="text-sm leading-5 text-muted-foreground">
                    {isAccumulation ? (
                      <>
                        Kalan tutar {formatMoney(progress.remaining_amount)}. Hedef tarihi:{" "}
                        {formatDate(goal.end_date)}.
                      </>
                    ) : (
                      <>
                        Şu ana kadar {formatMoney(progress.actual_spending)} harcandı. Kalan limit{" "}
                        {formatMoney(progress.remaining_limit)}. Hedef dönemi:{" "}
                        {formatDate(goal.start_date)}-{formatDate(goal.end_date)}.
                      </>
                    )}
                  </p>
                </div>
              ) : null}
              <p className="mt-auto pt-4 text-xs font-bold uppercase tracking-[0.16em] text-primary">
                Detaya bak
              </p>
            </article>
          );
        })}
      </section>

      {selectedGoal ? (
        <section className="ledger-card rounded-[1.8rem] border border-border/80 bg-card p-5 sm:p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                Hedef detayı
              </p>
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

          <div className="mt-5 grid gap-3 rounded-[1.4rem] border border-dashed border-primary/25 bg-primary/5 p-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
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
                  disabled={actionGoalId === selectedGoal.id || selectedGoal.status !== "active"}
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
                disabled={actionGoalId === selectedGoal.id || selectedGoal.status === "completed"}
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
                    className="h-full rounded-full bg-primary transition-all"
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
                  <div className="rounded-2xl bg-primary/10 p-3">
                    <p className="text-xs text-muted-foreground">
                      {selectedIsAccumulation ? "Hedef tutar" : "Hedef limit"}
                    </p>
                    <p className="font-display text-xl font-bold text-primary">
                      {formatMoney(
                        selectedIsAccumulation
                          ? selectedGoal.target_amount
                          : selectedGoal.target_spending_amount,
                      )}
                    </p>
                  </div>
                  <div className="rounded-2xl bg-accent/10 p-3">
                    <p className="text-xs text-muted-foreground">
                      {selectedIsAccumulation ? "Kalan" : "Kalan limit"}
                    </p>
                    <p className="font-display text-xl font-bold text-accent-foreground">
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

                <div className="rounded-[1.4rem] border border-border/70 bg-muted/35 p-4">
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
                          className="h-full rounded-full bg-primary"
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
                          className="h-full rounded-full bg-accent"
                          style={{ width: barWidth(selectedTargetValue, selectedChartMax) }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <aside className="rounded-[1.4rem] border border-dashed border-primary/30 bg-primary/5 p-4">
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
        </section>
      ) : null}
    </main>
  );
}
