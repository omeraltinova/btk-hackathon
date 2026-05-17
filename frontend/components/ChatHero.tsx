"use client";

import { MessageSquareText, ShieldCheck, Sparkles } from "lucide-react";

import { useKidMode } from "@/lib/kid-mode";

export function ChatHero() {
  const { isKid } = useKidMode();

  if (isKid) {
    return (
      <section className="ledger-sheet p-4 sm:p-5">
        <div className="relative z-10 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <span className="kid-chip">
              <Sparkles className="h-4 w-4" />
              Koç sohbeti
            </span>
            <h1 className="kid-hero-title mt-2 text-3xl sm:text-4xl">Aklındaki soruyu sor.</h1>
          </div>
          <div className="rounded-2xl bg-background/65 px-4 py-3 text-sm leading-6 sm:max-w-md">
            Harçlık, kumbara veya merak ettiğin kavramları yaz; koçun kısa ve tanıdık örneklerle
            cevaplar.
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="ledger-sheet p-4 sm:p-5">
      <div className="relative z-10 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <span className="stamp-label bg-background/70">
            <MessageSquareText className="h-3.5 w-3.5" />
            Koç modu
          </span>
          <h1 className="mt-2 font-display text-3xl font-black leading-none tracking-[-0.05em] sm:text-4xl">
            Sohbet, kanıtıyla birlikte akar.
          </h1>
        </div>
        <div className="receipt-tape max-w-xl rotate-0 px-4 py-3">
          <div className="flex items-start gap-2 text-sm leading-6">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <p>
              Araç çağrıları ayrı sekmede kalır; geçmiş konuşmalar aynı sohbet içinde bağlam olarak
              taşınır.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
