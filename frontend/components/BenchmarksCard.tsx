"use client";

import { Info, TrendingDown, TrendingUp } from "lucide-react";

import { amountToKurus, formatKurus } from "@/lib/format";
import type { TransactionCategoryTotal } from "@/lib/types";
import { cn } from "@/lib/utils";

// Anonymized reference values for an "average Turkish household" by category, in TL.
// These are illustrative benchmarks chosen to give the user a sense of where they
// sit relative to a hypothetical similar family. They are not derived from any
// real consumer panel — labeled accordingly in the UI to avoid implying authority.
const HOUSEHOLD_BENCHMARKS: Record<string, number> = {
  market: 4500,
  fatura: 2200,
  ulasim: 1800,
  ulaşım: 1800,
  okul: 1500,
  egitim: 1500,
  eğitim: 1500,
  harclik: 900,
  harçlık: 900,
  yemek: 1600,
  akaryakit: 1700,
  akaryakıt: 1700,
  telekom: 600,
  ev: 3000,
  eğlence: 700,
  eglence: 700,
};

type BenchmarksCardProps = {
  categoryTotals: TransactionCategoryTotal[];
};

function normalizeKey(name: string): string {
  return name.toLocaleLowerCase("tr-TR").trim();
}

function matchBenchmark(categoryName: string): number | null {
  const key = normalizeKey(categoryName);
  if (key in HOUSEHOLD_BENCHMARKS) return HOUSEHOLD_BENCHMARKS[key] ?? null;
  for (const benchmarkKey of Object.keys(HOUSEHOLD_BENCHMARKS)) {
    if (key.includes(benchmarkKey)) return HOUSEHOLD_BENCHMARKS[benchmarkKey] ?? null;
  }
  return null;
}

export function BenchmarksCard({ categoryTotals }: BenchmarksCardProps) {
  const rows = categoryTotals
    .map((entry) => {
      const benchmark = matchBenchmark(entry.category_name);
      if (benchmark === null) return null;
      const benchmarkKurus = Math.round(benchmark * 100);
      const actualKurus = amountToKurus(entry.amount);
      if (actualKurus <= 0) return null;
      const deltaKurus = actualKurus - benchmarkKurus;
      const deltaPercent = benchmarkKurus > 0 ? (deltaKurus / benchmarkKurus) * 100 : 0;
      return {
        categoryName: entry.category_name,
        actualKurus,
        benchmarkKurus,
        deltaKurus,
        deltaPercent,
      };
    })
    .filter((row): row is NonNullable<typeof row> => row !== null)
    .sort((first, second) => Math.abs(second.deltaKurus) - Math.abs(first.deltaKurus))
    .slice(0, 4);

  if (rows.length === 0) return null;

  return (
    <section className="ledger-card rounded-[1.6rem] border border-border/80 bg-card p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
            Benzer ailelere göre
          </p>
          <h2 className="mt-1 font-display text-xl font-black sm:text-2xl">
            Karşılaştırmalı kategori bandı
          </h2>
        </div>
        <span className="inline-flex items-center gap-1 rounded-full bg-muted/55 px-2 py-1 text-[0.65rem] font-bold uppercase tracking-[0.16em] text-muted-foreground">
          <Info className="h-3 w-3" />
          Yaklaşık değer
        </span>
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Aşağıdaki rakamlar gerçek tüketici paneli verisi değildir; benzer büyüklükteki Türk aileleri
        için yaklaşık referans aralıklarıdır.
      </p>
      <ul className="mt-4 space-y-3">
        {rows.map((row) => {
          const above = row.deltaKurus > 0;
          const exact = row.deltaKurus === 0;
          const Icon = exact ? null : above ? TrendingUp : TrendingDown;
          const max = Math.max(row.actualKurus, row.benchmarkKurus, 1);
          const actualPercent = Math.max(2, Math.min(100, (row.actualKurus / max) * 100));
          const benchmarkPercent = Math.max(2, Math.min(100, (row.benchmarkKurus / max) * 100));
          return (
            <li
              key={row.categoryName}
              className="rounded-2xl border border-border/70 bg-muted/30 p-3"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <span className="font-display text-base font-black">{row.categoryName}</span>
                <span
                  className={cn(
                    "inline-flex items-center gap-1 text-xs font-bold",
                    exact ? "text-muted-foreground" : above ? "text-destructive" : "text-primary",
                  )}
                >
                  {Icon !== null ? <Icon className="h-3 w-3" /> : null}
                  {exact
                    ? "Eşit"
                    : `${above ? "+" : "-"}${Math.round(Math.abs(row.deltaPercent))}% (${formatKurus(Math.abs(row.deltaKurus))})`}
                </span>
              </div>
              <div className="mt-2 space-y-1.5">
                <div>
                  <div className="flex items-center justify-between text-[0.65rem] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                    <span>Sen</span>
                    <span>{formatKurus(row.actualKurus)}</span>
                  </div>
                  <div className="mt-1 h-2 overflow-hidden rounded-full bg-background">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${actualPercent}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex items-center justify-between text-[0.65rem] font-bold uppercase tracking-[0.14em] text-muted-foreground">
                    <span>Benzer aile ortalaması</span>
                    <span>{formatKurus(row.benchmarkKurus)}</span>
                  </div>
                  <div className="mt-1 h-2 overflow-hidden rounded-full bg-background">
                    <div
                      className="h-full rounded-full bg-accent transition-all"
                      style={{ width: `${benchmarkPercent}%` }}
                    />
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
