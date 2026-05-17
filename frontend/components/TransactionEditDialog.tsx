"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { categoriesForType, hasCategoryForType } from "@/lib/category-groups";
import { toDateTimeLocal, toIsoDateTime } from "@/lib/datetime";
import { amountInput, isValidAmount, normalizeAmountInput } from "@/lib/money-input";
import type { Category, Transaction, TransactionType, TransactionUpdateInput } from "@/lib/types";

const selectClassName =
  "flex h-11 w-full rounded-2xl border border-input bg-background/80 px-4 py-2 text-sm ring-offset-background transition-all duration-200 ease-quint focus-visible:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

type TransactionDraft = {
  amount: string;
  type: TransactionType;
  categoryId: string;
  merchant: string;
  description: string;
  occurredAt: string;
};

type TransactionEditDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  transaction: Transaction | null;
  categories: Category[];
  title?: string;
  description?: string;
  onSave: (transactionId: string, payload: TransactionUpdateInput) => Promise<void>;
};

function transactionToDraft(transaction: Transaction): TransactionDraft {
  return {
    amount: amountInput(transaction.amount),
    type: transaction.type,
    categoryId: transaction.category_id ?? "",
    merchant: transaction.merchant ?? "",
    description: transaction.description ?? "",
    occurredAt: toDateTimeLocal(transaction.occurred_at),
  };
}

export function TransactionEditDialog({
  open,
  onOpenChange,
  transaction,
  categories,
  title = "İşlemi düzenle",
  description = "Tutar, tarih, kategori ve not alanlarını güncelleyebilirsin.",
  onSave,
}: TransactionEditDialogProps) {
  const [draft, setDraft] = useState<TransactionDraft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const visibleCategories = useMemo(
    () => (draft ? categoriesForType(categories, draft.type) : []),
    [categories, draft],
  );

  useEffect(() => {
    if (!open || !transaction) return;
    setDraft(transactionToDraft(transaction));
    setError(null);
  }, [open, transaction]);

  function handleTypeChange(nextType: TransactionType) {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        type: nextType,
        categoryId: hasCategoryForType(categories, current.categoryId, nextType)
          ? current.categoryId
          : "",
      };
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!transaction || !draft) return;
    const normalizedAmount = normalizeAmountInput(draft.amount);
    if (!isValidAmount(normalizedAmount)) {
      setError("Tutarı 1250,50 biçiminde girer misin?");
      return;
    }
    if (!draft.occurredAt) {
      setError("İşlem için tarih ve saat seç.");
      return;
    }
    const merchant = draft.merchant.trim();
    if (!merchant) {
      setError("Satıcı veya kaynak zorunlu.");
      return;
    }

    const payload: TransactionUpdateInput = {
      amount: normalizedAmount,
      type: draft.type,
      category_id: draft.categoryId || null,
      merchant,
      description: draft.description || null,
      occurred_at: toIsoDateTime(draft.occurredAt),
    };

    setIsSaving(true);
    setError(null);
    try {
      await onSave(transaction.id, payload);
      onOpenChange(false);
    } catch {
      setError("İşlem güncellenemedi, tekrar dener misin?");
    } finally {
      setIsSaving(false);
    }
  }

  if (!transaction || !draft) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] w-[calc(100vw-1.5rem)] overflow-hidden rounded-[1.5rem] p-4 sm:max-w-3xl sm:p-6">
        <DialogHeader>
          <DialogTitle className="font-display text-3xl font-black">{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <form className="max-h-[72vh] space-y-4 overflow-y-auto pr-1" onSubmit={handleSubmit}>
          {error ? (
            <p className="bg-destructive/14 rounded-2xl border border-destructive/35 px-4 py-3 text-sm font-semibold text-foreground shadow-sm">
              {error}
            </p>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor="edit-transaction-type" className="text-sm font-medium">
                Tür
              </label>
              <select
                id="edit-transaction-type"
                className={selectClassName}
                value={draft.type}
                onChange={(event) => handleTypeChange(event.target.value as TransactionType)}
              >
                <option value="expense">Gider</option>
                <option value="income">Gelir</option>
              </select>
            </div>
            <div className="space-y-2">
              <label htmlFor="edit-transaction-amount" className="text-sm font-medium">
                Tutar
              </label>
              <Input
                id="edit-transaction-amount"
                inputMode="decimal"
                value={draft.amount}
                onChange={(event) =>
                  setDraft((current) =>
                    current ? { ...current, amount: event.target.value } : current,
                  )
                }
                required
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor="edit-transaction-category" className="text-sm font-medium">
                Kategori
              </label>
              <select
                id="edit-transaction-category"
                className={selectClassName}
                value={draft.categoryId}
                onChange={(event) =>
                  setDraft((current) =>
                    current ? { ...current, categoryId: event.target.value } : current,
                  )
                }
              >
                <option value="">Kategori seçme</option>
                {visibleCategories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                    {category.user_id ? " · özel" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label htmlFor="edit-transaction-date" className="text-sm font-medium">
                Tarih ve saat
              </label>
              <Input
                id="edit-transaction-date"
                type="datetime-local"
                value={draft.occurredAt}
                onChange={(event) =>
                  setDraft((current) =>
                    current ? { ...current, occurredAt: event.target.value } : current,
                  )
                }
                required
              />
            </div>
          </div>

          <div className="space-y-2">
            <label htmlFor="edit-transaction-merchant" className="text-sm font-medium">
              Satıcı veya kaynak
            </label>
            <Input
              id="edit-transaction-merchant"
              value={draft.merchant}
              onChange={(event) =>
                setDraft((current) =>
                  current ? { ...current, merchant: event.target.value } : current,
                )
              }
              placeholder="Örn. Migros, maaş, kira"
              required
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="edit-transaction-description" className="text-sm font-medium">
              Not
            </label>
            <Input
              id="edit-transaction-description"
              value={draft.description}
              onChange={(event) =>
                setDraft((current) =>
                  current ? { ...current, description: event.target.value } : current,
                )
              }
              placeholder="Kısa açıklama"
            />
          </div>

          <Button type="submit" className="w-full" disabled={isSaving}>
            {isSaving ? "Kaydediliyor..." : "İşlemi güncelle"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
