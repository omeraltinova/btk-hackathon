"use client";

import {
  AlertCircle,
  CheckCircle2,
  ImagePlus,
  Loader2,
  MessageSquareText,
  ReceiptText,
  UploadCloud,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { type ChangeEvent, type DragEvent, useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { ReceiptConfirmDialog } from "@/components/ReceiptConfirmDialog";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { rememberPendingChatMessage } from "@/lib/chat-session";
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

function ErrorNote({ children }: { children: string }) {
  return (
    <p className="bg-destructive/14 flex items-center gap-2 rounded-2xl border border-destructive/35 px-4 py-3 text-sm font-semibold text-foreground shadow-sm">
      <AlertCircle className="h-4 w-4 text-destructive" />
      {children}
    </p>
  );
}

type ReceiptUploaderProps = {
  showHistory?: boolean;
  onConfirmed?: (transaction: Transaction) => void;
};

export function ReceiptUploader({ showHistory = true, onConfirmed }: ReceiptUploaderProps) {
  const router = useRouter();
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
  const [lastConfirmed, setLastConfirmed] = useState<Transaction | null>(null);

  const loadData = useCallback(async () => {
    setError(null);
    try {
      const [categoryData, transactionData] = await Promise.all([
        api<Category[]>("/api/categories", { silent: true }),
        showHistory
          ? api<Transaction[]>("/api/transactions?limit=100", { silent: true })
          : Promise.resolve<Transaction[]>([]),
      ]);
      setCategories(sortCategories(categoryData));
      setTransactions(transactionData);
    } catch (err) {
      setError(friendlyError(err, "Fiş verileri yüklenemedi, biraz sonra tekrar dener misin?"));
    } finally {
      setIsLoading(false);
    }
  }, [showHistory]);

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
      if (showHistory) setTransactions((current) => [created, ...current]);
      onConfirmed?.(created);
      setCandidate(null);
      setIsConfirmOpen(false);
      setLastConfirmed(created);
      toast.success("Fiş işleme dönüştü.");
    } catch (err) {
      setError(friendlyError(err, "Fiş işleme yazılamadı, tekrar dener misin?"));
    } finally {
      setIsSubmitting(false);
    }
  }

  function askCoachAboutMerchant(transaction: Transaction) {
    const merchant = transaction.merchant?.trim();
    const message = merchant
      ? `${merchant}'a bu ay ne kadar harcadım?`
      : "Bu ay markete ne kadar harcadım?";
    rememberPendingChatMessage({
      source: "dashboard",
      title: merchant ? `${merchant} harcaması` : "Fiş harcaması",
      startNew: true,
      message,
    });
    router.push("/chat");
  }

  return (
    <>
      {lastConfirmed ? (
        <div className="mb-4 flex flex-col gap-3 rounded-[1.4rem] border border-primary/40 bg-primary/10 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div className="flex min-w-0 items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
            <div className="min-w-0">
              <p className="font-display text-lg font-bold leading-tight">Fiş işleme dönüştü.</p>
              <p className="mt-1 truncate text-sm text-muted-foreground">
                {lastConfirmed.merchant ?? "Fiş"} ·{" "}
                {formatKurus(amountToKurus(lastConfirmed.amount))}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" size="sm" onClick={() => askCoachAboutMerchant(lastConfirmed)}>
              <MessageSquareText className="h-4 w-4" />
              Koça sor
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-label="Bildirimi kapat"
              onClick={() => setLastConfirmed(null)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ) : null}

      <div className="grid min-w-0 gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <section className="ledger-sheet p-4 sm:p-6">
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
                "grid min-h-80 cursor-pointer place-items-center rounded-[1.5rem] border border-dashed border-primary/55 bg-secondary/45 p-5 text-center transition-colors sm:min-h-96 sm:p-6",
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
                  <h2 className="font-display text-[2rem] font-black leading-none sm:text-3xl">
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

            {error ? <ErrorNote>{error}</ErrorNote> : null}
          </div>
        </section>

        <section className="receipt-tape rotate-[-0.75deg] p-6 pt-9">
          <div className="flex items-start justify-between gap-4 border-b border-dashed border-border pb-5">
            <div>
              <p className="font-display text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">
                OCR önizleme
              </p>
              <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
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
                <p className="mt-2 break-words font-display text-[2.25rem] font-black tabular-nums leading-none text-primary sm:text-4xl">
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

          <div className="bg-primary/14 mt-7 flex items-center gap-2 rounded-[1rem] p-4 text-sm font-semibold text-foreground">
            <CheckCircle2 className="h-4 w-4" />
            Kullanıcı onayı olmadan işlem yazılmaz.
          </div>
        </section>
      </div>

      {showHistory ? (
        <section className="space-y-3">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Fiş geçmişi</p>
              <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
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
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
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
                      <div className="sm:text-right">
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
      ) : null}

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
