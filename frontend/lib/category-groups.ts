import type { Category, TransactionType } from "@/lib/types";

const INCOME_CATEGORY_NAMES = new Set([
  "maaş",
  "harçlık",
  "staj",
  "hediye",
  "freelance",
  "faiz geliri",
  "diğer gelir",
]);

const EXPENSE_CATEGORY_NAMES = new Set([
  "market",
  "fatura",
  "ulaşım",
  "kira",
  "eğitim",
  "sağlık",
  "eğlence",
  "giyim",
  "yemek",
  "akaryakıt",
  "telekom",
  "ev",
  "bakım",
  "birikim",
  "diğer",
]);

function normalizedCategoryName(category: Category): string {
  return category.name.trim().toLocaleLowerCase("tr-TR");
}

function isEnvelopeManagedCategory(category: Category): boolean {
  return category.budget_monthly !== null;
}

export function categoryMatchesType(category: Category, type: TransactionType): boolean {
  const name = normalizedCategoryName(category);
  if (category.user_id !== null) {
    if (type === "income") {
      return !isEnvelopeManagedCategory(category) && !EXPENSE_CATEGORY_NAMES.has(name);
    }
    return !INCOME_CATEGORY_NAMES.has(name) || EXPENSE_CATEGORY_NAMES.has(name);
  }
  return type === "income" ? INCOME_CATEGORY_NAMES.has(name) : EXPENSE_CATEGORY_NAMES.has(name);
}

export function categoriesForType(categories: Category[], type: TransactionType): Category[] {
  return categories.filter((category) => categoryMatchesType(category, type));
}

export function hasCategoryForType(
  categories: Category[],
  categoryId: string,
  type: TransactionType,
): boolean {
  return categoriesForType(categories, type).some((category) => category.id === categoryId);
}
