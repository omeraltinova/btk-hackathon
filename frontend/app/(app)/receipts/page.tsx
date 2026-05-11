import { CheckCircle2, ImagePlus, ReceiptText, ScanLine, UploadCloud } from "lucide-react";

export const metadata = {
  title: "Fişler — Cüzdan Koçu",
};

const receiptSteps = [
  "Fişi yükle",
  "Gemini Vision satırları okur",
  "Kategori önerisi gelir",
  "Onayınla işleme dönüşür",
] as const;

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
              4. günde burada gerçek sürükle-bırak, önizleme ve OCR sonucu olacak. Şimdilik ekran,
              fişin güvenli biçimde işleme dönüşeceği yolu gösteriyor.
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
          </div>
        </aside>
      </section>

      <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <section className="ledger-sheet p-5 sm:p-6">
          <div className="relative z-10 grid min-h-96 place-items-center rounded-[1.5rem] border border-dashed border-primary/55 bg-secondary/45 p-6 text-center transition-colors hover:bg-secondary/60">
            <div className="space-y-5">
              <span className="float-gentle hard-shadow-accent mx-auto grid h-20 w-20 place-items-center rounded-[1.5rem_1.5rem_0.8rem_1.5rem] bg-primary text-primary-foreground">
                <UploadCloud className="h-8 w-8" />
              </span>
              <div>
                <h2 className="font-display text-3xl font-black tracking-[-0.04em]">
                  Fişi masaya bırak
                </h2>
                <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
                  Maks 5 MB. 4. günde görsel seçimi, yükleme durumu ve OCR önizlemesi bağlanır.
                </p>
              </div>
              <span className="stamp-label mx-auto bg-background/70 text-muted-foreground">
                <ImagePlus className="h-3.5 w-3.5" />
                JPG veya PNG
              </span>
            </div>
          </div>
        </section>

        <section className="receipt-tape rotate-[-0.75deg] p-6 pt-9">
          <div className="flex items-start justify-between gap-4 border-b border-dashed border-border pb-5">
            <div>
              <p className="font-display text-xs font-bold uppercase tracking-[0.22em] text-muted-foreground">
                OCR önizleme
              </p>
              <h2 className="mt-2 font-display text-3xl font-black tracking-[-0.04em]">
                Migros fişi örneği
              </h2>
            </div>
            <ReceiptText className="h-6 w-6 text-primary" />
          </div>

          <div className="mt-5 flex items-center justify-between gap-4">
            <div>
              <p className="font-display text-2xl font-black">Migros</p>
              <p className="text-sm text-muted-foreground">Kategori: Market</p>
            </div>
            <p className="font-display text-2xl font-black tabular-nums">247,50 ₺</p>
          </div>

          <div className="mt-6 space-y-3">
            {receiptSteps.map((step, index) => (
              <div key={step} className="grid grid-cols-[2rem_1fr] items-center gap-3">
                <span className="grid h-8 w-8 place-items-center rounded-full bg-primary text-sm font-bold text-primary-foreground">
                  {index + 1}
                </span>
                <p className="font-semibold">{step}</p>
              </div>
            ))}
          </div>

          <div className="mt-7 flex items-center gap-2 rounded-[1rem] bg-primary/10 p-4 text-sm font-semibold text-primary">
            <CheckCircle2 className="h-4 w-4" />
            Kullanıcı onayı olmadan işlem yazılmaz.
          </div>
        </section>
      </div>

      <div className="tab-chip hard-shadow-primary bg-card/90 p-5 pr-8">
        <div className="flex items-center gap-3">
          <ScanLine className="h-5 w-5 text-primary" />
          <p className="font-semibold">Yükleme yolu: /api/receipts/upload</p>
        </div>
      </div>
    </div>
  );
}
