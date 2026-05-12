import { ShieldCheck } from "lucide-react";

import { ReceiptUploader } from "@/components/ReceiptUploader";

export const metadata = {
  title: "Fişler — Cüzdan Koçu",
};

export default function ReceiptsPage() {
  return (
    <div className="page-enter space-y-8">
      <section className="grid gap-5 lg:grid-cols-[1fr_0.52fr] lg:items-stretch">
        <div className="ledger-sheet binder-holes p-6 pl-8 sm:p-9 sm:pl-20">
          <div className="relative z-10 max-w-3xl space-y-5">
            <span className="stamp-label bg-background/70">Fiş akışı</span>
            <h1 className="font-display text-[clamp(2.4rem,5.5vw,5.2rem)] font-black leading-[0.94] tracking-[-0.05em]">
              Fotoğrafı bütçeye çeviren onay masası.
            </h1>
            <p className="max-w-[64ch] text-lg leading-8 text-muted-foreground">
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

      <ReceiptUploader />
    </div>
  );
}
