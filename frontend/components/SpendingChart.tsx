"use client";

import { ChartPie } from "lucide-react";

import { amountToKurus, formatKurus } from "@/lib/format";
import type { TransactionSummary } from "@/lib/types";

const pieColors = [
  "oklch(var(--primary))",
  "oklch(var(--accent))",
  "oklch(0.58 0.13 52)",
  "oklch(0.64 0.1 192)",
  "oklch(0.62 0.11 310)",
  "oklch(0.68 0.12 25)",
];

function formatPlainPercent(value: string): string {
  const parsed = Number(value.replace(",", "."));
  if (!Number.isFinite(parsed)) return `%${value}`;
  return `%${new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(parsed)}`;
}

type SpendingChartProps = {
  summary: TransactionSummary | null;
};

export function SpendingChart({ summary }: SpendingChartProps) {
  const totals = summary?.category_totals ?? [];
  const total = totals.reduce((sum, item) => sum + amountToKurus(item.amount), 0);
  let offset = 0;
  const slices = totals.map((item, index) => {
    const percent = total === 0 ? 0 : (amountToKurus(item.amount) / total) * 100;
    const slice = {
      item,
      percent,
      offset,
      color: pieColors[index % pieColors.length],
    };
    offset += percent;
    return slice;
  });

  return (
    <section className="receipt-tape p-5 pt-8 sm:p-6 sm:pt-9">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Kategori dağılımı</p>
          <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
            Bu ayki gider pastası
          </h2>
        </div>
        <ChartPie className="h-6 w-6 text-primary" />
      </div>

      {total === 0 ? (
        <div className="bg-background/72 mt-8 rounded-[2rem] border border-dashed border-primary/30 p-6">
          <p className="font-display text-xl font-black">Pasta için gider bekleniyor</p>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Kategorili ilk giderini eklediğinde dağılım burada gerçek veriden çizilecek.
          </p>
        </div>
      ) : (
        <div className="mt-7 grid gap-6 sm:grid-cols-[13rem_1fr] sm:items-center">
          <svg viewBox="0 0 36 36" className="mx-auto h-44 w-44 -rotate-90 sm:h-48 sm:w-48">
            <circle
              cx="18"
              cy="18"
              r="15.9155"
              fill="none"
              stroke="oklch(var(--muted))"
              strokeWidth="5.8"
            />
            {slices.map((slice) => (
              <circle
                key={slice.item.category_id ?? slice.item.category_name}
                cx="18"
                cy="18"
                r="15.9155"
                fill="none"
                stroke={slice.color}
                strokeDasharray={`${slice.percent} ${100 - slice.percent}`}
                strokeDashoffset={-slice.offset}
                strokeLinecap="round"
                strokeWidth="5.8"
              />
            ))}
          </svg>
          <div className="space-y-3">
            {slices.map((slice) => (
              <div
                key={slice.item.category_id ?? slice.item.category_name}
                className="flex flex-col gap-3 rounded-2xl bg-background/70 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="flex items-center gap-3">
                  <span className="h-3 w-3 rounded-full" style={{ backgroundColor: slice.color }} />
                  <div>
                    <p className="text-sm font-bold">{slice.item.category_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {formatPlainPercent(slice.item.percentage)}
                    </p>
                  </div>
                </div>
                <p className="font-display text-lg font-black tabular-nums sm:text-right">
                  {formatKurus(amountToKurus(slice.item.amount))}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
