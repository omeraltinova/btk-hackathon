"use client";

import { PiggyBank, Target } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError, api } from "@/lib/api";
import { isValidAmount, normalizeAmountInput } from "@/lib/money-input";
import { cn } from "@/lib/utils";
import type { Category, SavingGoal, SavingGoalProgress } from "@/lib/types";

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

function friendlyError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

export function SavingGoalsClient() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [goals, setGoals] = useState<SavingGoal[]>([]);
  const [progressByGoalId, setProgressByGoalId] = useState<Record<string, SavingGoalProgress>>({});
  const [mode, setMode] = useState<GoalMode>("accumulation");
  const [selectedCategoryId, setSelectedCategoryId] = useState("");
  const [targetReductionPercent, setTargetReductionPercent] = useState("15");
  const [accumulationTitle, setAccumulationTitle] = useState("Tatil birikimi");
  const [targetAmount, setTargetAmount] = useState("20000");
  const [currentAmount, setCurrentAmount] = useState("0");
  const [targetDate, setTargetDate] = useState(defaultTargetDate);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  async function loadGoals() {
    const [categoryRows, goalRows] = await Promise.all([
      api<Category[]>("/api/categories", { silent: true }),
      api<SavingGoal[]>("/api/saving-goals?status=active", { silent: true }),
    ]);
    setCategories(categoryRows);
    setGoals(goalRows);
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

  const accumulationGoals = goals.filter((goal) => goal.goal_type === "accumulation");
  const reductionGoals = goals.filter((goal) => goal.goal_type === "expense_reduction");

  return (
    <main className="space-y-6 p-4 sm:p-6 lg:p-8">
      <section className="receipt-tape hard-shadow relative overflow-hidden rounded-[2rem] border border-border/80 bg-card p-5 sm:p-7">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem] lg:items-end">
          <div className="max-w-2xl space-y-3">
            <span className="stamp-label bg-primary/10 text-primary">Akıllı hedefler</span>
            <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
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
              <>
                <label className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                  Hedef adı
                </label>
                <Input
                  value={accumulationTitle}
                  onChange={(event) => setAccumulationTitle(event.target.value)}
                />
                <label className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                  Hedef tutar
                </label>
                <Input
                  inputMode="decimal"
                  value={targetAmount}
                  onChange={(event) => setTargetAmount(event.target.value)}
                />
                <label className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                  Şu an ayrılan tutar
                </label>
                <Input
                  inputMode="decimal"
                  value={currentAmount}
                  onChange={(event) => setCurrentAmount(event.target.value)}
                />
                <label className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                  Hedef tarih
                </label>
                <Input
                  type="date"
                  value={targetDate}
                  onChange={(event) => setTargetDate(event.target.value)}
                />
              </>
            ) : (
              <>
                <label className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                  Kategori
                </label>
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
                <label className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                  Azaltma hedefi (%)
                </label>
                <Input
                  inputMode="decimal"
                  value={targetReductionPercent}
                  onChange={(event) => setTargetReductionPercent(event.target.value)}
                />
              </>
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

      <section className="grid gap-4 lg:grid-cols-2">
        {goals.length === 0 ? (
          <div className="ledger-card rounded-[1.5rem] border border-border/80 bg-card p-6 text-sm text-muted-foreground lg:col-span-2">
            Henüz aktif hedef yok. Birikim tutarı veya gider azaltma hedefiyle başlayabilirsin.
          </div>
        ) : null}

        {[...accumulationGoals, ...reductionGoals].map((goal) => {
          const progress = progressByGoalId[goal.id];
          const progressWidth = progress
            ? Math.max(0, Math.min(100, Number(progress.progress_percent)))
            : 0;
          const isAccumulation = goal.goal_type === "accumulation";
          return (
            <article
              key={goal.id}
              className={cn(
                "ledger-card rounded-[1.5rem] border border-border/80 bg-card p-5",
                isAccumulation ? "bg-primary/5" : "",
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                    {isAccumulation ? "Birikim" : goal.category_name}
                  </p>
                  <h2 className="mt-1 font-display text-2xl font-bold">{goal.title}</h2>
                </div>
                <span className="rounded-full bg-secondary px-3 py-1 text-xs font-bold text-secondary-foreground">
                  {progress ? statusLabel(progress.status_label) : "Yükleniyor"}
                </span>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <div className="rounded-2xl bg-muted/60 p-3">
                  <p className="text-xs text-muted-foreground">
                    {isAccumulation ? "Şu an" : "Geçen dönem"}
                  </p>
                  <p className="font-display text-xl font-bold">
                    {formatMoney(isAccumulation ? goal.current_amount : goal.baseline_amount)}
                  </p>
                </div>
                <div className="rounded-2xl bg-primary/10 p-3">
                  <p className="text-xs text-muted-foreground">
                    {isAccumulation ? "Hedef tutar" : "Bu ay limit"}
                  </p>
                  <p className="font-display text-xl font-bold text-primary">
                    {formatMoney(isAccumulation ? goal.target_amount : goal.target_spending_amount)}
                  </p>
                </div>
                <div className="rounded-2xl bg-accent/10 p-3">
                  <p className="text-xs text-muted-foreground">
                    {isAccumulation ? "Aylık katkı" : "Beklenen tasarruf"}
                  </p>
                  <p className="font-display text-xl font-bold text-accent-foreground">
                    {formatMoney(
                      isAccumulation ? goal.monthly_contribution : goal.target_saving_amount,
                    )}
                  </p>
                </div>
              </div>

              {progress ? (
                <div className="mt-5 space-y-3">
                  <div className="h-3 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${progressWidth}%` }}
                    />
                  </div>
                  <p className="text-sm text-muted-foreground">
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
                  <ul className="space-y-2 text-sm text-foreground/80">
                    {progress.tactics.slice(0, 3).map((tactic) => (
                      <li key={tactic} className="rounded-xl bg-muted/45 px-3 py-2">
                        {tactic}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </article>
          );
        })}
      </section>
    </main>
  );
}
