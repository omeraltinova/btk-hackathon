"use client";

import { MessageSquare, Plus, ReceiptText, Sparkles } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

type EmptyDashboardHeroProps = {
  isKid: boolean;
};

export function EmptyDashboardHero({ isKid }: EmptyDashboardHeroProps) {
  if (isKid) {
    return (
      <section className="ledger-card relative overflow-hidden rounded-[1.8rem] border border-primary/35 bg-primary/5 p-5 sm:p-6">
        <span className="kid-chip">
          <Sparkles className="h-4 w-4" />
          Hoş geldin
        </span>
        <h2 className="kid-hero-title mt-2 text-2xl sm:text-3xl">Kumbara burada başlıyor!</h2>
        <p className="mt-2 max-w-prose text-sm leading-6 text-muted-foreground sm:text-base">
          İlk harçlığını veya bir alışverişini ekle, kumbaran hemen şekillenmeye başlar.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button asChild size="sm">
            <Link href="/transactions">
              <Plus className="h-4 w-4" />
              Hareket ekle
            </Link>
          </Button>
          <Button asChild size="sm" variant="secondary">
            <Link href="/chat">
              <MessageSquare className="h-4 w-4" />
              Koça sor
            </Link>
          </Button>
        </div>
      </section>
    );
  }

  return (
    <section className="ledger-card relative overflow-hidden rounded-[1.8rem] border border-primary/40 bg-primary/5 p-5 sm:p-6">
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
        <div className="space-y-3">
          <span className="stamp-label bg-background/70 text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            Yeni başlangıç
          </span>
          <h2 className="font-display text-[1.6rem] font-black leading-tight sm:text-2xl">
            Cüzdan Koçu seni dinlemeye hazır. Hadi ilk veriyi girelim.
          </h2>
          <p className="max-w-[58ch] text-sm leading-6 text-muted-foreground">
            Bir işlem, bir fiş ya da sohbette tek soru — koç o veriden başlayarak senin için
            harcamayı kategorize eder ve proaktif notlar üretir.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 lg:flex-col lg:items-stretch">
          <Button asChild size="sm">
            <Link href="/transactions">
              <Plus className="h-4 w-4" />
              İşlem ekle
            </Link>
          </Button>
          <Button asChild size="sm" variant="secondary">
            <Link href="/transactions">
              <ReceiptText className="h-4 w-4" />
              Fiş tara
            </Link>
          </Button>
          <Button asChild size="sm" variant="outline">
            <Link href="/chat">
              <MessageSquare className="h-4 w-4" />
              Sohbette sor
            </Link>
          </Button>
        </div>
      </div>
    </section>
  );
}
