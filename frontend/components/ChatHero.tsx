"use client";

import { MessageSquareText, ShieldCheck, Sparkles } from "lucide-react";

import { useKidMode } from "@/lib/kid-mode";

export function ChatHero() {
  const { isKid } = useKidMode();

  if (isKid) {
    return (
      <section className="ledger-sheet p-5 sm:p-8">
        <div className="relative z-10 space-y-6">
          <span className="kid-chip">
            <Sparkles className="h-4 w-4" />
            Koç sohbeti
          </span>
          <div className="space-y-3">
            <h1 className="kid-hero-title">Aklındaki soruyu sor, koçun cevaplasın.</h1>
            <p className="text-sm leading-6 text-muted-foreground sm:text-base">
              "Harçlığımı nasıl biriktiririm?" ya da "Faiz nedir?" gibi soruları sorabilirsin. Koçun
              seni anlayacağın bir dille cevaplar.
            </p>
          </div>
          <div className="rounded-3xl bg-background/65 p-4 text-sm leading-6">
            <p className="font-bold">İpucu</p>
            <p className="mt-1 text-muted-foreground">
              Cevaplar dondurma, oyuncak ya da kumbara gibi tanıdık örneklerle gelir.
            </p>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="ledger-sheet binder-holes p-5 pl-8 sm:p-8 sm:pl-16">
      <div className="relative z-10 space-y-7">
        <span className="stamp-label bg-background/70">
          <MessageSquareText className="h-3.5 w-3.5" />
          Koç modu
        </span>
        <div className="space-y-3">
          <h1 className="font-display text-[2.75rem] font-black leading-[0.95] tracking-[-0.05em] sm:text-5xl">
            Sohbet sayfası, cevap kadar kanıt da gösterir.
          </h1>
          <p className="text-foreground/78 max-w-[58ch] text-base leading-7">
            Akışlı cevaplar araç çağrılarıyla birlikte görünür; kullanıcı hangi veriye dayanarak
            cevap aldığını anlayabilir.
          </p>
        </div>
        <div className="receipt-tape rotate-[-1deg] px-5 py-7">
          <div className="flex items-center gap-2 text-sm font-bold">
            <ShieldCheck className="h-4 w-4 text-primary" />
            Gizlilik kuralı
          </div>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">
            Kullanıcı kimliği mesajdan okunmaz; güvenli oturum durumundan gelir.
          </p>
        </div>
      </div>
    </section>
  );
}
