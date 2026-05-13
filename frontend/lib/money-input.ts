export function amountInput(value: string): string {
  return value.replace(".", ",");
}

export function normalizeAmountInput(value: string): string {
  return value.replace(/\./g, "").replace(",", ".");
}

export function isValidAmount(value: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(value);
}
