"use client";

import { Copy, Crown, Share2, Sparkles, Wallet } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { amountToKurus, formatKurus } from "@/lib/format";
import type { TransactionSummary } from "@/lib/types";

type MonthlySummaryShareCardProps = {
  summary: TransactionSummary | null;
};

function periodLabel(periodStart: string): string {
  return new Intl.DateTimeFormat("tr-TR", {
    month: "long",
    year: "numeric",
    timeZone: "Europe/Istanbul",
  }).format(new Date(periodStart));
}

function plainPercent(value: string): string {
  const parsed = Number(value.replace(",", "."));
  if (!Number.isFinite(parsed)) return value;
  return `%${new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(parsed)}`;
}

export function MonthlySummaryShareCard({ summary }: MonthlySummaryShareCardProps) {
  const [open, setOpen] = useState(false);

  const period = useMemo(() => (summary ? periodLabel(summary.period_start) : ""), [summary]);

  if (summary === null) return null;

  const incomeKurus = amountToKurus(summary.income);
  const expenseKurus = amountToKurus(summary.expense);
  const balanceKurus = amountToKurus(summary.balance);
  const topCategories = [...summary.category_totals]
    .sort((first, second) => amountToKurus(second.amount) - amountToKurus(first.amount))
    .slice(0, 3);
  const biggest = topCategories[0] ?? null;
  const savedRate = incomeKurus > 0 ? Math.round((balanceKurus / incomeKurus) * 100) : null;

  function buildShareText(): string {
    const lines: string[] = [];
    lines.push(`${period} — Cüzdan Koçu özeti`);
    lines.push(`Gelir: ${formatKurus(incomeKurus)}`);
    lines.push(`Gider: ${formatKurus(expenseKurus)}`);
    lines.push(`Net: ${formatKurus(balanceKurus)}`);
    if (savedRate !== null) {
      lines.push(`Tasarruf oranı: %${savedRate}`);
    }
    if (biggest !== null) {
      lines.push(
        `En yüksek kategori: ${biggest.category_name} — ${formatKurus(amountToKurus(biggest.amount))}`,
      );
    }
    if (topCategories.length > 0) {
      lines.push("Top kategoriler:");
      for (const item of topCategories) {
        lines.push(
          `• ${item.category_name}: ${formatKurus(amountToKurus(item.amount))} (${plainPercent(item.percentage)})`,
        );
      }
    }
    return lines.join("\n");
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(buildShareText());
      toast.success("Özet metni panoya kopyalandı.");
    } catch {
      toast.error("Metin kopyalanamadı, tekrar dener misin?");
    }
  }

  async function handleShare() {
    const text = buildShareText();
    if (typeof navigator !== "undefined" && typeof navigator.share === "function") {
      try {
        await navigator.share({ title: `${period} — Cüzdan Koçu`, text });
        return;
      } catch {
        // User cancelled or share failed — fall through to clipboard.
      }
    }
    await handleCopy();
  }

  return (
    <>
      <Button type="button" size="sm" variant="secondary" onClick={() => setOpen(true)}>
        <Share2 className="h-4 w-4" />
        Aylık özet kartı
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[92vh] w-[calc(100vw-1.5rem)] overflow-y-auto rounded-[1.5rem] p-4 sm:max-w-2xl sm:p-6">
          <DialogHeader>
            <DialogTitle className="font-display text-2xl font-black">Aylık özet kartı</DialogTitle>
            <DialogDescription>
              {period} için kısa bir özet kartı. Kopyalayıp paylaşabilir veya tarayıcının yazdır
              menüsünden PDF olarak kaydedebilirsin.
            </DialogDescription>
          </DialogHeader>

          <div className="receipt-tape relative overflow-hidden rounded-[1.4rem] border border-border/80 bg-card p-5 sm:p-6">
            <div className="flex items-start justify-between gap-3">
              <div>
                <span className="stamp-label bg-primary/15 text-primary">
                  <Sparkles className="h-3.5 w-3.5" />
                  Cüzdan Koçu
                </span>
                <p className="mt-2 font-display text-3xl font-black tracking-tight">{period}</p>
                <p className="text-sm text-muted-foreground">Aile bütçesi özetin</p>
              </div>
              <Wallet className="h-8 w-8 text-primary" />
            </div>

            <div className="mt-4 grid gap-2 sm:grid-cols-3">
              <div className="rounded-2xl bg-background/70 p-3">
                <p className="text-[0.65rem] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  Gelir
                </p>
                <p className="mt-1 font-display text-xl font-black tabular-nums text-primary">
                  {formatKurus(incomeKurus)}
                </p>
              </div>
              <div className="rounded-2xl bg-background/70 p-3">
                <p className="text-[0.65rem] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  Gider
                </p>
                <p className="mt-1 font-display text-xl font-black tabular-nums text-accent-foreground">
                  {formatKurus(expenseKurus)}
                </p>
              </div>
              <div className="rounded-2xl bg-background/70 p-3">
                <p className="text-[0.65rem] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  Net
                </p>
                <p
                  className="mt-1 font-display text-xl font-black tabular-nums"
                  style={{
                    color: balanceKurus >= 0 ? "oklch(var(--primary))" : "oklch(0.6 0.18 25)",
                  }}
                >
                  {formatKurus(balanceKurus)}
                </p>
              </div>
            </div>

            {biggest !== null ? (
              <div className="mt-4 flex items-start gap-3 rounded-2xl bg-accent/15 p-3">
                <Crown className="mt-0.5 h-4 w-4 shrink-0 text-accent-foreground" />
                <div className="min-w-0">
                  <p className="text-[0.65rem] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                    Bu ayın en yüksek kategorisi
                  </p>
                  <p className="font-display text-lg font-black">
                    {biggest.category_name} — {formatKurus(amountToKurus(biggest.amount))}
                  </p>
                </div>
              </div>
            ) : null}

            {topCategories.length > 0 ? (
              <div className="mt-4">
                <p className="text-[0.65rem] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                  Top 3 kategori
                </p>
                <ul className="mt-2 space-y-1.5">
                  {topCategories.map((item) => (
                    <li
                      key={item.category_id ?? item.category_name}
                      className="flex items-center justify-between gap-3 text-sm"
                    >
                      <span className="truncate font-bold">{item.category_name}</span>
                      <span className="tabular-nums text-muted-foreground">
                        {formatKurus(amountToKurus(item.amount))} ({plainPercent(item.percentage)})
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {savedRate !== null ? (
              <div className="mt-4 rounded-2xl bg-primary/10 p-3 text-sm">
                <p className="font-bold">
                  Tasarruf oranı: <span className="text-primary">%{savedRate}</span>
                </p>
                <p className="text-xs text-muted-foreground">
                  Gelirinin yaklaşık {Math.max(0, savedRate)}%&apos;si bu ay kumbarada kaldı.
                </p>
              </div>
            ) : null}

            <p className="mt-5 border-t border-dashed border-border pt-3 text-[0.65rem] uppercase tracking-[0.18em] text-muted-foreground">
              cüzdan koçu · aile bütçe defteri
            </p>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-end gap-2">
            <Button type="button" size="sm" variant="outline" onClick={handleCopy}>
              <Copy className="h-4 w-4" />
              Metni kopyala
            </Button>
            <Button type="button" size="sm" onClick={handleShare}>
              <Share2 className="h-4 w-4" />
              Paylaş
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
