"use client";

import { ShieldCheck, Sticker } from "lucide-react";

import { useKidMode } from "@/lib/kid-mode";

export function ReceiptHero() {
  const { isKid } = useKidMode();

  if (isKid) {
    return (
      <section className="ledger-sheet p-5 sm:p-8">
        <div className="relative z-10 max-w-3xl space-y-5">
          <span className="kid-chip">
            <Sticker className="h-4 w-4" />
            Fiş yükle
          </span>
          <h1 className="kid-hero-title">Fişin fotoğrafını çek, koç gerisini halletsin.</h1>
          <p className="text-sm leading-6 text-muted-foreground sm:text-base">
            Bir şey aldığında fişin fotoğrafını yükleyebilirsin. Koç fişi okur, sen onayladıktan
            sonra cüzdanına eklenir.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="grid min-w-0 gap-5 lg:grid-cols-[1fr_0.52fr] lg:items-stretch">
      <div className="ledger-sheet binder-holes p-5 pl-8 sm:p-9 sm:pl-20">
        <div className="relative z-10 max-w-3xl space-y-5">
          <span className="stamp-label bg-background/70">Fiş akışı</span>
          <h1 className="font-display text-[clamp(2.55rem,12vw,5.2rem)] font-black leading-[0.94] tracking-[-0.05em]">
            Fotoğrafı bütçeye çeviren onay masası.
          </h1>
          <p className="text-foreground/78 max-w-[64ch] text-base leading-7 sm:text-lg sm:leading-8">
            Fişi yükle, OCR sonucunu düzenle ve yalnızca onayladığında gider olarak kaydet. Geçmiş
            listesi doğrudan veritabanındaki fiş kaynaklı işlemlerden gelir.
          </p>
        </div>
      </div>

      <aside className="cash-envelope p-6">
        <div className="relative z-10 space-y-4">
          <span className="stamp-label bg-background/70">Gizlilik</span>
          <h2 className="font-display text-2xl font-black tracking-[-0.03em]">
            Ham OCR çıktısı loglanmaz
          </h2>
          <p className="text-sm leading-6 text-muted-foreground">
            Fiş görseli ve ham OCR verisi hassastır. Sistem yalnızca olay tipini ve güvenli
            kullanıcı kaydını loglar.
          </p>
          <ShieldCheck className="h-6 w-6 text-primary" />
        </div>
      </aside>
    </section>
  );
}
