"use client";

import { ChartPie } from "lucide-react";
import { useState } from "react";

import { amountToKurus, formatKurus } from "@/lib/format";
import type { TransactionSummary } from "@/lib/types";

const pieColors = [
  "oklch(var(--primary))",
  "oklch(var(--accent))",
  "oklch(0.58 0.13 52)",
  "oklch(0.64 0.1 192)",
  "oklch(0.62 0.11 310)",
  "oklch(0.68 0.12 25)",
  "oklch(0.55 0.12 235)",
  "oklch(0.66 0.1 165)",
  "oklch(0.6 0.12 350)",
  "oklch(0.72 0.11 105)",
  "oklch(0.5 0.1 285)",
  "oklch(0.7 0.12 15)",
];

function generatedPieColor(index: number): string {
  const hue = (index * 137.508 + 143) % 360;
  const lightness = 0.54 + (index % 4) * 0.055;
  const chroma = 0.105 + (index % 3) * 0.018;
  return `oklch(${lightness.toFixed(3)} ${chroma.toFixed(3)} ${hue.toFixed(1)})`;
}

function pieColor(index: number): string {
  return pieColors[index] ?? generatedPieColor(index);
}

function formatPlainPercent(value: string): string {
  const parsed = Number(value.replace(",", "."));
  if (!Number.isFinite(parsed)) return `%${value}`;
  return `%${new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(parsed)}`;
}

type SpendingChartProps = {
  summary: TransactionSummary | null;
};

type ActiveSlice = {
  amount: string;
  color: string;
  name: string;
  percentage: string;
};

export function SpendingChart({ summary }: SpendingChartProps) {
  const [activeSlice, setActiveSlice] = useState<ActiveSlice | null>(null);
  const totals = summary?.category_totals ?? [];
  const total = totals.reduce((sum, item) => sum + amountToKurus(item.amount), 0);
  let offset = 0;
  const slices = totals.map((item, index) => {
    const percent = total === 0 ? 0 : (amountToKurus(item.amount) / total) * 100;
    const slice = {
      item,
      percent,
      offset,
      color: pieColor(index),
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
          <div className="spending-pie-shell relative mx-auto h-44 w-44 sm:h-48 sm:w-48">
            <svg viewBox="0 0 36 36" className="spending-pie-wheel h-full w-full">
              <circle
                cx="18"
                cy="18"
                r="15.9155"
                fill="none"
                stroke="oklch(var(--muted))"
                strokeWidth="5.8"
              />
              {slices.map((slice) => {
                const name = slice.item.category_name;
                const percentage = formatPlainPercent(slice.item.percentage);
                const amount = formatKurus(amountToKurus(slice.item.amount));
                return (
                  <circle
                    key={slice.item.category_id ?? slice.item.category_name}
                    aria-label={`${name}: ${amount}, ${percentage}`}
                    className="spending-pie-slice"
                    cx="18"
                    cy="18"
                    r="15.9155"
                    fill="none"
                    role="button"
                    stroke={slice.color}
                    strokeDasharray={`${slice.percent} ${100 - slice.percent}`}
                    strokeDashoffset={-slice.offset}
                    strokeLinecap="round"
                    strokeWidth="5.8"
                    tabIndex={0}
                    onBlur={() => setActiveSlice(null)}
                    onFocus={() => setActiveSlice({ amount, color: slice.color, name, percentage })}
                    onMouseEnter={() =>
                      setActiveSlice({ amount, color: slice.color, name, percentage })
                    }
                    onMouseLeave={() => setActiveSlice(null)}
                  />
                );
              })}
            </svg>
            {activeSlice ? (
              <div className="spending-pie-center-label absolute left-1/2 top-1/2 w-[8.5rem] -translate-x-1/2 -translate-y-1/2 rounded-[1.25rem] bg-background/90 px-3 py-2 text-center shadow-sm backdrop-blur">
                <span
                  aria-hidden
                  className="mx-auto mb-1 block h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: activeSlice.color }}
                />
                <p className="truncate text-xs font-black text-foreground">{activeSlice.name}</p>
                <p className="mt-0.5 text-[0.68rem] font-bold text-muted-foreground">
                  {activeSlice.percentage} / {activeSlice.amount}
                </p>
              </div>
            ) : null}
          </div>
          <div className="spending-pie-details space-y-3">
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
