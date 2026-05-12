"use client";

import { CalendarDays, Loader2, Plus, ReceiptText, Trash2, WalletCards } from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import {
  formatDateTR,
  formatKurus,
  formatTransactionAmount,
  transactionAmountToKurus,
} from "@/lib/format";
import type { Transaction, TransactionCreateInput, TransactionType } from "@/lib/types";

function defaultDateTimeLocal(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function toIsoDateTime(value: string): string {
  return new Date(value).toISOString();
}

function normalizeAmountInput(value: string): string {
  return value.replace(/\./g, "").replace(",", ".");
}

function isValidAmount(value: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(value);
}

function isCurrentMonth(value: string): boolean {
  const date = new Date(value);
  const now = new Date();
  return date.getFullYear() === now.getFullYear() && date.getMonth() === now.getMonth();
}

export function DashboardClient() {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [type, setType] = useState<TransactionType>("expense");
  const [amount, setAmount] = useState("");
  const [merchant, setMerchant] = useState("");
  const [description, setDescription] = useState("");
  const [occurredAt, setOccurredAt] = useState(defaultDateTimeLocal);

  async function loadTransactions() {
    setError(null);
    try {
      const data = await api<Transaction[]>("/api/transactions", { silent: true });
      setTransactions(data);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.detail
          : "İşlemler yüklenemedi, biraz sonra tekrar dener misin?",
      );
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadTransactions();
  }, []);

  const monthly = useMemo(
    () => transactions.filter((tx) => isCurrentMonth(tx.occurred_at)),
    [transactions],
  );
  const monthlyExpense = monthly
    .filter((tx) => tx.type === "expense")
    .reduce((total, tx) => total + Math.abs(transactionAmountToKurus(tx.amount, tx.type)), 0);
  const monthlyIncome = monthly
    .filter((tx) => tx.type === "income")
    .reduce((total, tx) => total + transactionAmountToKurus(tx.amount, tx.type), 0);
  const balance = monthly.reduce(
    (total, tx) => total + transactionAmountToKurus(tx.amount, tx.type),
    0,
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    const normalizedAmount = normalizeAmountInput(amount);
    if (!isValidAmount(normalizedAmount)) {
      setError("Tutarı 1250,50 biçiminde girer misin?");
      setIsSubmitting(false);
      return;
    }
    const payload: TransactionCreateInput = {
      amount: normalizedAmount,
      type,
      merchant: merchant || null,
      description: description || null,
      occurred_at: toIsoDateTime(occurredAt),
    };

    try {
      const created = await api<Transaction>("/api/transactions", {
        method: "POST",
        body: payload,
        silent: true,
      });
      setTransactions((current) => [created, ...current]);
      setAmount("");
      setMerchant("");
      setDescription("");
      setOccurredAt(defaultDateTimeLocal());
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "İşlem kaydedilemedi, tekrar dener misin?");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete(transactionId: string) {
    setError(null);
    try {
      await api<void>(`/api/transactions/${transactionId}`, { method: "DELETE", silent: true });
      setTransactions((current) => current.filter((tx) => tx.id !== transactionId));
    } catch (err) {
      setError(err instanceof ApiError ? err.detail : "İşlem silinemedi, tekrar dener misin?");
    }
  }

  return (
    <div className="page-enter space-y-8">
      <section className="grid gap-5 lg:grid-cols-[1.05fr_0.75fr] lg:items-stretch">
        <div className="ledger-sheet binder-holes p-6 pl-8 sm:p-9 sm:pl-20">
          <div className="relative z-10 max-w-3xl space-y-6">
            <span className="stamp-label bg-background/70">Gerçek veri defteri</span>
            <div className="space-y-4">
              <h1 className="font-display text-[clamp(2.5rem,6vw,5.7rem)] font-black leading-[0.92] tracking-[-0.05em]">
                Bugünkü bütçe sayfası açıldı.
              </h1>
              <p className="max-w-[62ch] text-lg leading-8 text-muted-foreground">
                Bu panel yalnızca veritabanındaki işlemleri gösterir. İlk gelir veya giderini
                eklediğinde özet ve son işlemler otomatik güncellenir.
              </p>
            </div>
          </div>
        </div>

        <aside className="receipt-tape p-6 pt-9 text-sm leading-6 text-foreground">
          <p className="font-display text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">
            Koç notu
          </p>
          <div className="mt-5 flex items-start gap-3">
            <span className="pulse-soft grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent text-accent-foreground">
              <WalletCards className="h-5 w-5" />
            </span>
            <div>
              <h2 className="font-display text-2xl font-black leading-7">
                Veri eklemeye başlayabilirsin
              </h2>
              <p className="mt-3 text-muted-foreground">
                Proaktif uyarılar gerçek işlem verisi geldikçe üretilecek; boş defterde örnek
                harcama gösterilmiyor.
              </p>
            </div>
          </div>
        </aside>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        {[
          ["Bu ay gider", formatKurus(monthlyExpense), "Veritabanındaki gider toplamı"],
          ["Bu ay gelir", formatKurus(monthlyIncome), "Veritabanındaki gelir toplamı"],
          ["Net durum", formatKurus(balance), "Gelir eksi gider"],
        ].map(([label, value, detail], index) => (
          <div key={label} className="cash-envelope min-h-44 p-5">
            <div className="relative z-10 flex h-full flex-col justify-between gap-6">
              <p className="text-sm font-bold text-secondary-foreground/80">{label}</p>
              <div>
                <p className="font-display text-4xl font-black tabular-nums tracking-[-0.04em]">
                  {value}
                </p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
              </div>
              <span className="font-display text-xs font-bold text-primary/70">
                ZARF {index + 1}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
        <section className="ledger-sheet p-6 sm:p-8">
          <div className="relative z-10 space-y-6">
            <div>
              <p className="eyebrow">Manuel giriş</p>
              <h2 className="mt-2 font-display text-3xl font-black tracking-[-0.04em]">
                Yeni işlem ekle
              </h2>
            </div>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="space-y-2">
                  <label htmlFor="transaction-type" className="text-sm font-medium">
                    Tür
                  </label>
                  <select
                    id="transaction-type"
                    className="flex h-11 w-full rounded-2xl border border-input bg-background/80 px-4 py-2 text-sm ring-offset-background transition-all duration-200 ease-quint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    value={type}
                    onChange={(event) => setType(event.target.value as TransactionType)}
                  >
                    <option value="expense">Gider</option>
                    <option value="income">Gelir</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <label htmlFor="transaction-amount" className="text-sm font-medium">
                    Tutar
                  </label>
                  <Input
                    id="transaction-amount"
                    inputMode="decimal"
                    placeholder="Tutar gir"
                    value={amount}
                    onChange={(event) => setAmount(event.target.value)}
                    required
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label htmlFor="transaction-merchant" className="text-sm font-medium">
                  Satıcı veya kaynak
                </label>
                <Input
                  id="transaction-merchant"
                  value={merchant}
                  onChange={(event) => setMerchant(event.target.value)}
                  placeholder="Örn. market, maaş, fatura"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="transaction-description" className="text-sm font-medium">
                  Not
                </label>
                <Input
                  id="transaction-description"
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  placeholder="Kısa açıklama"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="transaction-date" className="text-sm font-medium">
                  Tarih ve saat
                </label>
                <Input
                  id="transaction-date"
                  type="datetime-local"
                  value={occurredAt}
                  onChange={(event) => setOccurredAt(event.target.value)}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Kaydediliyor..." : "İşlemi kaydet"}
                <Plus className="h-4 w-4" />
              </Button>
            </form>
          </div>
        </section>

        <section className="space-y-3">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Veritabanı kayıtları</p>
              <h2 className="mt-2 font-display text-3xl font-black tracking-[-0.04em]">
                Son işlemler
              </h2>
            </div>
            <ReceiptText className="h-6 w-6 text-primary" />
          </div>

          {error ? (
            <p className="rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm font-medium text-destructive">
              {error}
            </p>
          ) : null}

          {isLoading ? (
            <div className="receipt-tape flex items-center gap-3 px-5 py-6 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              İşlemler yükleniyor...
            </div>
          ) : transactions.length === 0 ? (
            <div className="receipt-tape px-5 py-8">
              <CalendarDays className="h-6 w-6 text-primary" />
              <h3 className="mt-4 font-display text-2xl font-black">Henüz işlem yok</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                İlk gerçek gelir veya giderini eklediğinde bu bölüm veritabanından dolacak.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {transactions.map((item) => (
                <div
                  key={item.id}
                  className="receipt-tape flex items-center justify-between gap-4 px-5 py-6 transition-transform duration-300 ease-quint motion-safe:hover:-rotate-1"
                >
                  <div>
                    <p className="font-display text-lg font-black">
                      {item.merchant ?? item.description ?? "İsimsiz işlem"}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {item.type === "income" ? "Gelir" : "Gider"} /{" "}
                      {formatDateTR(item.occurred_at)}
                    </p>
                    {item.description && item.description !== item.merchant ? (
                      <p className="mt-1 text-xs text-muted-foreground">{item.description}</p>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-3 text-right">
                    <div>
                      <p className="font-display text-xl font-black tabular-nums">
                        {formatTransactionAmount(item.amount, item.type)}
                      </p>
                      <p className="text-xs font-bold text-muted-foreground">
                        {item.source === "manual" ? "Manuel" : "Otomatik"}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      aria-label="İşlemi sil"
                      onClick={() => void handleDelete(item.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
