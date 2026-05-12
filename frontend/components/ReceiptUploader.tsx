"use client";

import {
  AlertCircle,
  CheckCircle2,
  ImagePlus,
  Loader2,
  ReceiptText,
  UploadCloud,
} from "lucide-react";
import { type ChangeEvent, type DragEvent, useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { ReceiptConfirmDialog } from "@/components/ReceiptConfirmDialog";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { amountToKurus, formatDateTR, formatKurus } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { Category, ReceiptCandidate, Transaction, TransactionCreateInput } from "@/lib/types";

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function sortCategories(categories: Category[]): Category[] {
  return [...categories].sort((first, second) => {
    const ownership = Number(first.user_id !== null) - Number(second.user_id !== null);
    if (ownership !== 0) return ownership;
    return first.name.localeCompare(second.name, "tr");
  });
}

function friendlyError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

export function ReceiptUploader() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [candidate, setCandidate] = useState<ReceiptCandidate | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isConfirmOpen, setIsConfirmOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [categoryData, transactionData] = await Promise.all([
        api<Category[]>("/api/categories", { silent: true }),
        api<Transaction[]>("/api/transactions?limit=100", { silent: true }),
      ]);
      setCategories(sortCategories(categoryData));
      setTransactions(transactionData);
    } catch (err) {
      setError(friendlyError(err, "Fiş verileri yüklenemedi, biraz sonra tekrar dener misin?"));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const categoryNameById = useMemo(
    () => new Map(categories.map((category) => [category.id, category.name])),
    [categories],
  );

  const receiptTransactions = useMemo(
    () => transactions.filter((transaction) => transaction.source === "receipt_ocr"),
    [transactions],
  );

  async function uploadFile(file: File) {
    if (!ACCEPTED_TYPES.has(file.type)) {
      setError("Yalnızca JPG, PNG veya WEBP fişi yükleyebilirsin.");
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setError("Fiş dosyası en fazla 5 MB olmalı.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    const nextPreviewUrl = URL.createObjectURL(file);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(nextPreviewUrl);
    setError(null);
    setIsUploading(true);
    try {
      const uploaded = await api<ReceiptCandidate>("/api/receipts/upload", {
        method: "POST",
        body: formData,
        silent: true,
      });
      setCandidate(uploaded);
      setIsConfirmOpen(true);
    } catch (err) {
      setError(friendlyError(err, "Fiş okunamadı, daha net bir fotoğrafla tekrar dener misin?"));
    } finally {
      setIsUploading(false);
    }
  }

  function handleInputChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) void uploadFile(file);
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void uploadFile(file);
  }

  async function handleConfirm(payload: TransactionCreateInput) {
    setIsSubmitting(true);
    setError(null);
    try {
      const created = await api<Transaction>("/api/transactions", {
        method: "POST",
        body: payload,
        silent: true,
      });
      setTransactions((current) => [created, ...current]);
      setCandidate(null);
      setIsConfirmOpen(false);
      toast.success("Fiş işleme dönüştü.");
    } catch (err) {
      setError(friendlyError(err, "Fiş işleme yazılamadı, tekrar dener misin?"));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <section className="ledger-sheet p-5 sm:p-6">
          <div className="relative z-10 space-y-5">
            <label
              htmlFor="receipt-file"
              onDragOver={(event) => {
                event.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={handleDrop}
              className={cn(
                "grid min-h-96 cursor-pointer place-items-center rounded-[1.5rem] border border-dashed border-primary/55 bg-secondary/45 p-6 text-center transition-colors",
                isDragging ? "bg-primary/15" : "hover:bg-secondary/60",
              )}
            >
              <input
                id="receipt-file"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                disabled={isUploading}
                onChange={handleInputChange}
              />
              <div className="space-y-5">
                <span className="float-gentle hard-shadow-accent mx-auto grid h-20 w-20 place-items-center rounded-[1.5rem_1.5rem_0.8rem_1.5rem] bg-primary text-primary-foreground">
                  {isUploading ? (
                    <Loader2 className="h-8 w-8 animate-spin" />
                  ) : (
                    <UploadCloud className="h-8 w-8" />
                  )}
                </span>
                <div>
                  <h2 className="font-display text-3xl font-black tracking-[-0.04em]">
                    Fişi masaya bırak
                  </h2>
                  <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
                    JPG, PNG veya WEBP. Maksimum 5 MB.
                  </p>
                </div>
                <span className="stamp-label mx-auto bg-background/70 text-muted-foreground">
                  <ImagePlus className="h-3.5 w-3.5" />
                  {isUploading ? "OCR okunuyor" : "Görsel seç"}
                </span>
              </div>
            </label>

            {error ? (
              <p className="flex items-center gap-2 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm font-medium text-destructive">
                <AlertCircle className="h-4 w-4" />
                {error}
              </p>
            ) : null}
          </div>
        </section>

        <section className="receipt-tape rotate-[-0.75deg] p-6 pt-9">
          <div className="flex items-start justify-between gap-4 border-b border-dashed border-border pb-5">
            <div>
              <p className="font-display text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">
                OCR önizleme
              </p>
              <h2 className="mt-2 font-display text-3xl font-black tracking-[-0.04em]">
                {candidate ? "Fiş adayı hazır" : "OCR sonucu bekleniyor"}
              </h2>
            </div>
            <ReceiptText className="h-6 w-6 text-primary" />
          </div>

          {candidate ? (
            <div className="mt-5 space-y-4">
              <div className="rounded-[1.25rem] border border-dashed border-border/80 p-5">
                <p className="font-display text-2xl font-black">
                  {candidate.merchant ?? "Fişten aktarılan gider"}
                </p>
                <p className="mt-2 font-display text-4xl font-black tabular-nums text-primary">
                  {formatKurus(amountToKurus(candidate.amount))}
                </p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  {candidate.category_name ?? "Kategorisiz"} / {formatDateTR(candidate.occurred_at)}
                </p>
              </div>
              <Button type="button" className="w-full" onClick={() => setIsConfirmOpen(true)}>
                Önizlemeyi aç
                <CheckCircle2 className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <div className="mt-5 rounded-[1.25rem] border border-dashed border-border/80 p-5">
              <p className="font-display text-2xl font-black">Henüz fiş yüklenmedi</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Fiş yüklendiğinde veritabanına yazılmadan önce gerçek OCR sonucu burada görünecek.
              </p>
            </div>
          )}

          <div className="mt-7 flex items-center gap-2 rounded-[1rem] bg-primary/10 p-4 text-sm font-semibold text-primary">
            <CheckCircle2 className="h-4 w-4" />
            Kullanıcı onayı olmadan işlem yazılmaz.
          </div>
        </section>
      </div>

      <section className="space-y-3">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="eyebrow">Fiş geçmişi</p>
            <h2 className="mt-2 font-display text-3xl font-black tracking-[-0.04em]">
              Onaylanan fişler
            </h2>
          </div>
          <ReceiptText className="h-6 w-6 text-primary" />
        </div>

        {isLoading ? (
          <div className="receipt-tape flex items-center gap-3 px-5 py-6 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Fiş geçmişi yükleniyor...
          </div>
        ) : receiptTransactions.length === 0 ? (
          <div className="receipt-tape px-5 py-8">
            <ReceiptText className="h-6 w-6 text-primary" />
            <h3 className="mt-4 font-display text-2xl font-black">Henüz onaylanan fiş yok</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              İlk fişi onayladığında burada veritabanından gelen işlem kaydı görünecek.
            </p>
          </div>
        ) : (
          <div className="grid gap-3 xl:grid-cols-2">
            {receiptTransactions.map((item) => {
              const categoryName = item.category_id
                ? (categoryNameById.get(item.category_id) ?? "Kategori")
                : "Kategorisiz";
              return (
                <div key={item.id} className="receipt-tape px-5 py-6">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="font-display text-lg font-black">
                        {item.merchant ?? item.description ?? "Fiş kaydı"}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {categoryName} / {formatDateTR(item.occurred_at)}
                      </p>
                      {item.description ? (
                        <p className="mt-1 text-xs text-muted-foreground">{item.description}</p>
                      ) : null}
                    </div>
                    <div className="text-right">
                      <p className="font-display text-xl font-black tabular-nums">
                        {formatKurus(amountToKurus(item.amount))}
                      </p>
                      <p className="text-xs font-bold text-muted-foreground">Fiş OCR</p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>

      <ReceiptConfirmDialog
        candidate={candidate}
        categories={categories}
        open={isConfirmOpen}
        isSubmitting={isSubmitting}
        previewUrl={previewUrl}
        onOpenChange={(open) => {
          if (!isSubmitting) setIsConfirmOpen(open);
        }}
        onConfirm={handleConfirm}
      />
    </>
  );
}
