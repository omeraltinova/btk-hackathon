"use client";

import { CheckCircle2, ReceiptText } from "lucide-react";
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
import { formatDateTR, formatKurus, amountToKurus } from "@/lib/format";
import type { Category, ReceiptCandidate, TransactionCreateInput } from "@/lib/types";

const selectClassName =
  "flex h-11 w-full rounded-2xl border border-input bg-background/80 px-4 py-2 text-sm ring-offset-background transition-all duration-200 ease-quint focus-visible:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

type ReceiptConfirmDialogProps = {
  candidate: ReceiptCandidate | null;
  categories: Category[];
  open: boolean;
  isSubmitting: boolean;
  previewUrl: string | null;
  onOpenChange: (open: boolean) => void;
  onConfirm: (payload: TransactionCreateInput) => Promise<void>;
};

function amountInput(value: string): string {
  return value.replace(".", ",");
}

function normalizeAmountInput(value: string): string {
  return value.replace(/\./g, "").replace(",", ".");
}

function isValidAmount(value: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(value);
}

function toLocalInput(value: string): string {
  const date = new Date(value);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function toIsoDateTime(value: string): string {
  return new Date(value).toISOString();
}

export function ReceiptConfirmDialog({
  candidate,
  categories,
  open,
  isSubmitting,
  previewUrl,
  onOpenChange,
  onConfirm,
}: ReceiptConfirmDialogProps) {
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [occurredAt, setOccurredAt] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (!candidate) return;
    setMerchant(candidate.merchant ?? "");
    setAmount(amountInput(candidate.amount));
    setOccurredAt(toLocalInput(candidate.occurred_at));
    setCategoryId(candidate.category_id ?? "");
    setDescription(candidate.description);
    setFormError(null);
  }, [candidate]);

  const confidenceLabel = useMemo(() => {
    if (!candidate) return "";
    const percentage = Math.round(Number(candidate.confidence) * 100);
    return Number.isFinite(percentage) ? `%${percentage}` : "%0";
  }, [candidate]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!candidate) return;

    const normalizedAmount = normalizeAmountInput(amount);
    if (!isValidAmount(normalizedAmount)) {
      setFormError("Tutarı 1250,50 biçiminde girer misin?");
      return;
    }
    const merchantValue = merchant.trim();
    if (!merchantValue) {
      setFormError("Satıcı zorunlu.");
      return;
    }

    setFormError(null);
    await onConfirm({
      amount: normalizedAmount,
      type: "expense",
      category_id: categoryId || null,
      merchant: merchantValue,
      description: description || null,
      occurred_at: toIsoDateTime(occurredAt),
      source: "receipt_ocr",
      receipt_image_url: candidate.receipt_image_url,
      raw_ocr_data: candidate.raw_ocr_data,
    });
  }

  if (!candidate) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] w-[calc(100vw-1.5rem)] overflow-y-auto rounded-[1.5rem] p-4 sm:max-w-3xl sm:p-6">
        <DialogHeader>
          <DialogTitle className="font-display text-3xl font-black">Fişi onayla</DialogTitle>
          <DialogDescription>
            İşleme yazılmadan önce tutarı, tarihi ve kategoriyi kontrol et.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="space-y-4">
            <div className="overflow-hidden rounded-[1.25rem] border border-border bg-muted/45">
              {previewUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={previewUrl}
                  alt="Fiş önizlemesi"
                  className="max-h-72 w-full object-cover"
                />
              ) : (
                <div className="grid h-56 place-items-center text-muted-foreground">
                  <ReceiptText className="h-8 w-8" />
                </div>
              )}
            </div>
            <div className="receipt-tape p-4">
              <div className="flex items-center justify-between gap-3 border-b border-dashed border-border pb-3">
                <span className="font-display text-xs font-bold uppercase text-muted-foreground">
                  OCR güveni
                </span>
                <span className="font-display text-lg font-black text-primary">
                  {confidenceLabel}
                </span>
              </div>
              <div className="mt-3 space-y-2 text-sm">
                {candidate.items.length === 0 ? (
                  <p className="text-muted-foreground">Satır kalemi bulunamadı.</p>
                ) : (
                  candidate.items.slice(0, 5).map((item) => (
                    <div key={`${item.name}-${item.amount}`} className="flex justify-between gap-3">
                      <span className="truncate">{item.name}</span>
                      <span className="font-bold tabular-nums">
                        {item.amount ? formatKurus(amountToKurus(item.amount)) : ""}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <label htmlFor="receipt-merchant" className="text-sm font-medium">
                  Satıcı
                </label>
                <Input
                  id="receipt-merchant"
                  value={merchant}
                  onChange={(event) => setMerchant(event.target.value)}
                  placeholder="Satıcı adı"
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="receipt-amount" className="text-sm font-medium">
                  Tutar
                </label>
                <Input
                  id="receipt-amount"
                  inputMode="decimal"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  required
                />
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <label htmlFor="receipt-date" className="text-sm font-medium">
                  Tarih ve saat
                </label>
                <Input
                  id="receipt-date"
                  type="datetime-local"
                  value={occurredAt}
                  onChange={(event) => setOccurredAt(event.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="receipt-category" className="text-sm font-medium">
                  Kategori
                </label>
                <select
                  id="receipt-category"
                  className={selectClassName}
                  value={categoryId}
                  onChange={(event) => setCategoryId(event.target.value)}
                >
                  <option value="">Kategori seçme</option>
                  {categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                      {category.user_id ? " · özel" : ""}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="receipt-description" className="text-sm font-medium">
                Not
              </label>
              <Input
                id="receipt-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Kısa açıklama"
              />
            </div>

            <div className="bg-primary/14 rounded-[1.25rem] p-4 text-sm font-semibold text-foreground">
              <CheckCircle2 className="mr-2 inline h-4 w-4" />
              Önerilen kayıt: {candidate.merchant ?? "Fiş"} / {formatDateTR(candidate.occurred_at)}
            </div>

            {formError ? (
              <p className="bg-destructive/14 rounded-2xl border border-destructive/35 px-4 py-3 text-sm font-semibold text-foreground shadow-sm">
                {formError}
              </p>
            ) : null}

            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? "İşleme yazılıyor..." : "Fişi işleme dönüştür"}
              <CheckCircle2 className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  );
}
