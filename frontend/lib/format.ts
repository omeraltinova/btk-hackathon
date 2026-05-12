export function amountToKurus(amount: string): number {
  const trimmed = amount.trim();
  const sign = trimmed.startsWith("-") ? -1 : 1;
  const normalized = trimmed.replace("-", "").replace(",", ".");
  const [whole = "0", fraction = ""] = normalized.split(".");
  const lira = Number.parseInt(whole, 10) || 0;
  const kurus = Number.parseInt(fraction.padEnd(2, "0").slice(0, 2), 10) || 0;
  return sign * (lira * 100 + kurus);
}

export function transactionAmountToKurus(amount: string, type: "income" | "expense"): number {
  const value = amountToKurus(amount);
  return type === "income" ? value : -value;
}

export function formatKurus(value: number): string {
  const sign = value < 0 ? "-" : "";
  const absolute = Math.abs(value);
  const lira = Math.trunc(absolute / 100);
  const kurus = String(absolute % 100).padStart(2, "0");
  return `${sign}${new Intl.NumberFormat("tr-TR").format(lira)},${kurus} ₺`;
}

export function formatTransactionAmount(amount: string, type: "income" | "expense"): string {
  return formatKurus(transactionAmountToKurus(amount, type));
}

export function formatDateTR(value: string): string {
  return new Intl.DateTimeFormat("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Europe/Istanbul",
  }).format(new Date(value));
}

export function formatPercentTR(value: string | null): string {
  if (value === null) return "Karşılaştırma yok";
  const numeric = Number(value.replace(",", "."));
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${new Intl.NumberFormat("tr-TR", {
    maximumFractionDigits: 1,
    minimumFractionDigits: 0,
  }).format(numeric)}%`;
}
