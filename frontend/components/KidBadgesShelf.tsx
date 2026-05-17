"use client";

import {
  BookOpen,
  Lock,
  PiggyBank,
  ReceiptText,
  Sparkles,
  Target,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useState } from "react";

import { ACTIVE_PROFILE_EVENT } from "@/lib/active-profile";
import { api } from "@/lib/api";
import { amountToKurus } from "@/lib/format";
import type { SavingGoal, Transaction } from "@/lib/types";
import { cn } from "@/lib/utils";

const LESSONS_PROGRESS_KEY = "cuzdan-kocu.learn.progress";

type BadgeDefinition = {
  id: string;
  title: string;
  detail: string;
  icon: LucideIcon;
  earned: boolean;
};

type KidBadgesShelfProps = {
  transactions: Transaction[];
  income: number;
  expense: number;
};

function readStartedLessons(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(LESSONS_PROGRESS_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed)
      ? parsed.filter((value): value is string => typeof value === "string")
      : [];
  } catch {
    return [];
  }
}

function progressPercent(goal: SavingGoal): number {
  const target =
    goal.goal_type === "accumulation"
      ? Number(goal.target_amount ?? "0")
      : Number(goal.target_spending_amount);
  if (!Number.isFinite(target) || target <= 0) return 0;
  const current = Number(goal.current_amount);
  if (!Number.isFinite(current)) return 0;
  return Math.max(0, Math.min(100, (current / target) * 100));
}

export function KidBadgesShelf({ transactions, income, expense }: KidBadgesShelfProps) {
  const [goals, setGoals] = useState<SavingGoal[]>([]);
  const [startedLessons, setStartedLessons] = useState<string[]>([]);

  useEffect(() => {
    setStartedLessons(readStartedLessons());
    function handleStorage(event: StorageEvent) {
      if (event.key === LESSONS_PROGRESS_KEY) setStartedLessons(readStartedLessons());
    }
    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const rows = await api<SavingGoal[]>("/api/saving-goals", { silent: true });
        if (!cancelled) setGoals(rows);
      } catch {
        // Silent: badges just fall back to locked state if goals can't load.
      }
    }
    void load();
    function handleProfileChange() {
      void load();
    }
    window.addEventListener(ACTIVE_PROFILE_EVENT, handleProfileChange);
    return () => {
      cancelled = true;
      window.removeEventListener(ACTIVE_PROFILE_EVENT, handleProfileChange);
    };
  }, []);

  const hasReceipt = transactions.some((transaction) => transaction.source === "receipt_ocr");
  const balanceKurus = income - expense;
  const accumulationGoals = goals.filter((goal) => goal.goal_type === "accumulation");
  const hasAccumulationProgress = accumulationGoals.some(
    (goal) => amountToKurus(goal.current_amount) > 0,
  );
  const hasGoalAt50 = goals.some(
    (goal) => goal.status === "completed" || progressPercent(goal) >= 50,
  );

  const badges: BadgeDefinition[] = [
    {
      id: "first_move",
      title: "İlk hareket",
      detail: "İlk işlemini kaydettin.",
      icon: Sparkles,
      earned: transactions.length > 0,
    },
    {
      id: "receipt_hero",
      title: "Fiş kahramanı",
      detail: "Bir fişi taradın.",
      icon: ReceiptText,
      earned: hasReceipt,
    },
    {
      id: "budget_warden",
      title: "Bütçe denetçisi",
      detail: "Bu ay kumbaran artıda.",
      icon: Wallet,
      earned: balanceKurus > 0,
    },
    {
      id: "goal_keeper",
      title: "Hedef bekçisi",
      detail: "Bir hedefi yarıyı geçirdin.",
      icon: Target,
      earned: hasGoalAt50,
    },
    {
      id: "piggy_filler",
      title: "Kumbara dolduran",
      detail: "Birikim hedefine katkı yaptın.",
      icon: PiggyBank,
      earned: hasAccumulationProgress,
    },
    {
      id: "lesson_curious",
      title: "Ders meraklısı",
      detail: "İlk dersi açtın.",
      icon: BookOpen,
      earned: startedLessons.length > 0,
    },
  ];

  const earnedCount = badges.filter((badge) => badge.earned).length;

  return (
    <div className="ledger-card rounded-[1.6rem] border border-border/70 bg-card/70 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
          Kazandığın rozetler
        </p>
        <p className="text-xs font-bold text-foreground">
          {earnedCount}/{badges.length}
        </p>
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {badges.map((badge) => {
          const Icon = badge.icon;
          return (
            <li
              key={badge.id}
              className={cn(
                "flex flex-col items-center gap-1.5 rounded-2xl border p-3 text-center transition-colors",
                badge.earned
                  ? "border-primary/45 bg-primary/10"
                  : "border-border/70 bg-muted/35 opacity-60",
              )}
              title={badge.earned ? badge.detail : `Henüz kazanılmadı — ${badge.detail}`}
            >
              <span
                className={cn(
                  "grid h-9 w-9 place-items-center rounded-full",
                  badge.earned ? "bg-primary text-primary-foreground" : "bg-background/80",
                )}
              >
                {badge.earned ? <Icon className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
              </span>
              <span className="font-display text-xs font-black leading-tight">{badge.title}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
