"use client";

import { BarChart3, PieChart as PieIcon, TrendingUp } from "lucide-react";
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

import type { ChatChartSpec } from "@/lib/types";

const PALETTE = [
  "oklch(var(--primary))",
  "oklch(var(--accent))",
  "oklch(0.62 0.11 310)",
  "oklch(0.64 0.1 192)",
  "oklch(0.58 0.13 52)",
  "oklch(0.68 0.12 25)",
];

function colorFor(index: number): string {
  return PALETTE[index % PALETTE.length] ?? "oklch(var(--primary))";
}

function formatTry(value: number): string {
  return `${new Intl.NumberFormat("tr-TR", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)} ₺`;
}

type ChatChartProps = {
  spec: ChatChartSpec;
};

export function ChatChart({ spec }: ChatChartProps) {
  const data = spec.data.filter((point) => Number.isFinite(point.value));
  const drawableData = spec.type === "monthly" ? data : data.filter((point) => point.value > 0);
  const hasPositiveValue = drawableData.some((point) => point.value > 0);
  if (drawableData.length === 0 || !hasPositiveValue) {
    return (
      <div className="rounded-2xl border border-dashed border-border/70 bg-background/60 p-4 text-sm text-muted-foreground">
        Grafik için yeterli veri yok.
      </div>
    );
  }

  return (
    <figure className="space-y-3 rounded-3xl border border-border/70 bg-card/85 p-4 shadow-sm">
      <figcaption className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-display text-base font-black leading-tight">{spec.title}</p>
          {spec.subtitle ? <p className="text-xs text-muted-foreground">{spec.subtitle}</p> : null}
        </div>
        <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          {spec.type === "pie" ? (
            <PieIcon className="h-4 w-4" />
          ) : spec.type === "monthly" ? (
            <TrendingUp className="h-4 w-4" />
          ) : (
            <BarChart3 className="h-4 w-4" />
          )}
        </span>
      </figcaption>

      {spec.type === "pie" ? (
        <PieView data={drawableData} />
      ) : spec.type === "monthly" ? (
        <MonthlyView data={drawableData} />
      ) : (
        <BarView data={drawableData} />
      )}
    </figure>
  );
}

function BarView({ data }: { data: ChatChartSpec["data"] }) {
  return (
    <div className="space-y-3">
      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 4, right: 12, bottom: 4, left: 8 }}
          >
            <CartesianGrid stroke="oklch(var(--border) / 0.6)" horizontal={false} />
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="label"
              width={92}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "oklch(var(--muted-foreground))", fontSize: 11, fontWeight: 700 }}
            />
            <Bar dataKey="value" radius={[0, 8, 8, 0]} barSize={16}>
              {data.map((point, index) => (
                <Cell key={`${point.label}-${index}`} fill={colorFor(index)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartLegend data={data} />
    </div>
  );
}

function PieView({ data }: { data: ChatChartSpec["data"] }) {
  const total = data.reduce((sum, point) => sum + point.value, 0) || 1;

  return (
    <div className="flex flex-wrap items-center gap-5">
      <div className="h-44 w-44 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="label"
              innerRadius={38}
              outerRadius={76}
              paddingAngle={2}
              stroke="oklch(var(--card))"
              strokeWidth={2}
            >
              {data.map((point, index) => (
                <Cell key={`${point.label}-${index}`} fill={colorFor(index)} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="grid min-w-0 flex-1 gap-1.5 text-xs">
        {data.map((point, index) => {
          const percent = Math.round((point.value / total) * 100);
          return (
            <li
              key={`${point.label}-legend-${index}`}
              className="flex items-center justify-between gap-3"
            >
              <span className="flex min-w-0 items-center gap-2">
                <span
                  aria-hidden
                  className="h-3 w-3 shrink-0 rounded-full"
                  style={{ backgroundColor: colorFor(index) }}
                />
                <span className="min-w-0 truncate font-medium">{point.label}</span>
              </span>
              <span className="font-display font-black tabular-nums">
                {point.value_formatted} · %{percent}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

type MonthlySeries = {
  key: string;
  label: string;
  total: number;
};

type MonthlyRow = {
  label: string;
  [key: string]: string | number;
};

function buildMonthlySeries(data: ChatChartSpec["data"]): MonthlySeries[] {
  const labels = Array.from(new Set(data.map((point) => point.series ?? "Tutar")));
  return labels.map((label, index) => ({
    key: `series_${index}`,
    label,
    total: data
      .filter((point) => (point.series ?? "Tutar") === label)
      .reduce((sum, point) => sum + point.value, 0),
  }));
}

function buildMonthlyRows(data: ChatChartSpec["data"], series: MonthlySeries[]): MonthlyRow[] {
  const seriesKeys = new Map(series.map((item) => [item.label, item.key]));
  return Array.from(new Set(data.map((point) => point.label))).map((label) => {
    const row: MonthlyRow = { label };
    series.forEach((item) => {
      row[item.key] = 0;
    });
    data
      .filter((point) => point.label === label)
      .forEach((point) => {
        const key = seriesKeys.get(point.series ?? "Tutar");
        if (!key) return;
        const current = typeof row[key] === "number" ? row[key] : 0;
        row[key] = current + point.value;
      });
    return row;
  });
}

function MonthlyView({ data }: { data: ChatChartSpec["data"] }) {
  const series = buildMonthlySeries(data).filter((item) => item.total > 0);
  const rows = buildMonthlyRows(data, series);

  return (
    <div className="space-y-3">
      <div className="h-60 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
            <CartesianGrid stroke="oklch(var(--border) / 0.6)" vertical={false} />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              tick={{ fill: "oklch(var(--muted-foreground))", fontSize: 11, fontWeight: 700 }}
            />
            <YAxis hide />
            <Tooltip
              cursor={{ fill: "oklch(var(--muted) / 0.35)" }}
              formatter={(value: number | string, name: string) => [formatTry(Number(value)), name]}
            />
            {series.map((item, index) => (
              <Bar
                key={item.key}
                dataKey={item.key}
                name={item.label}
                fill={colorFor(index)}
                radius={[7, 7, 0, 0]}
                maxBarSize={28}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <MonthlyLegend series={series} />
    </div>
  );
}

function MonthlyLegend({ series }: { series: MonthlySeries[] }) {
  return (
    <ul className="grid gap-1.5 text-xs sm:grid-cols-2">
      {series.map((item, index) => (
        <li key={item.key} className="flex items-center justify-between gap-3">
          <span className="flex min-w-0 items-center gap-2">
            <span
              aria-hidden
              className="h-3 w-3 shrink-0 rounded-full"
              style={{ backgroundColor: colorFor(index) }}
            />
            <span className="min-w-0 truncate font-medium">{item.label}</span>
          </span>
          <span className="font-display font-black tabular-nums">{formatTry(item.total)}</span>
        </li>
      ))}
    </ul>
  );
}

function ChartLegend({ data }: { data: ChatChartSpec["data"] }) {
  return (
    <ul className="grid gap-1.5 text-xs sm:grid-cols-2">
      {data.map((point, index) => (
        <li
          key={`${point.label}-value-${index}`}
          className="flex items-center justify-between gap-3"
        >
          <span className="flex min-w-0 items-center gap-2">
            <span
              aria-hidden
              className="h-3 w-3 shrink-0 rounded-full"
              style={{ backgroundColor: colorFor(index) }}
            />
            <span className="min-w-0 truncate font-medium">{point.label}</span>
          </span>
          <span className="font-display font-black tabular-nums">{point.value_formatted}</span>
        </li>
      ))}
    </ul>
  );
}
