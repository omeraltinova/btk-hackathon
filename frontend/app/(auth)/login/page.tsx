import { ArrowRight, LockKeyhole, ShieldCheck, Sparkles, Wallet } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const metadata = {
  title: "Giriş — Cüzdan Koçu",
};

/**
 * Day 1 placeholder.
 *
 * The form is shown for layout review only — it does NOT submit anywhere yet.
 * Day 2 will wire the submit handler to `/api/auth/login` and store the JWT
 * via `lib/api.ts` setToken(), then redirect to /dashboard.
 *
 * Design note: master_plan §12.1 specifies email + password (bcrypt).
 * Magic link is in §12.3 stretch and is NOT built unless we have time after Day 7.
 */
export default function LoginPage() {
  return (
    <div className="relative grid min-h-screen place-items-center overflow-hidden p-4 sm:p-6">
      <div className="page-enter grid w-full max-w-6xl gap-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
        <section className="ledger-sheet binder-holes hidden min-h-[640px] p-8 pl-20 lg:block">
          <div className="relative z-10 flex min-h-[570px] flex-col justify-between">
            <div>
              <span className="stamp-label bg-background/70">
                <Wallet className="h-3.5 w-3.5" />
                Cüzdan Koçu
              </span>
            </div>

            <div className="max-w-xl space-y-5">
              <p className="eyebrow">Sıfırdan 60 saniyeye</p>
              <h1 className="font-display text-[clamp(3.2rem,6vw,6.25rem)] font-black leading-[0.88] tracking-[-0.06em]">
                Bütçe takibini aile sohbetine yaklaştırıyoruz.
              </h1>
              <p className="text-lg leading-8 text-muted-foreground">
                Fiş, abonelik, harçlık ve finansal kavramlar tek yerde. Cevaplar Türkçe, ton
                arkadaşça, veri sınırları net.
              </p>
            </div>

            <div className="grid gap-3">
              <div className="receipt-tape float-gentle px-5 py-7">
                <div className="flex items-center gap-3">
                  <Sparkles className="h-5 w-5 text-primary" />
                  <p className="font-semibold">
                    Proaktif uyarı: market harcaması artıyor olabilir.
                  </p>
                </div>
              </div>
              <div className="receipt-tape px-5 py-7">
                <div className="flex items-center gap-3">
                  <ShieldCheck className="h-5 w-5 text-primary" />
                  <p className="font-semibold">Çocuk hesabı sadece kendi verisini görür.</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="receipt-tape w-full p-6 pt-10 sm:p-8 sm:pt-12">
          <div className="space-y-7">
            <div className="space-y-3 text-center">
              <span className="stamp-label mx-auto bg-background/70 text-primary">
                <LockKeyhole className="h-3.5 w-3.5" />
                Giriş fişi
              </span>
              <h2 className="font-display text-4xl font-black tracking-[-0.05em]">
                Cüzdan Koçu'na giriş
              </h2>
              <p className="text-sm text-muted-foreground">
                E-posta adresin ve şifrenle giriş yap.
              </p>
            </div>

            {/* Day 2: convert to client component, wire onSubmit to /api/auth/login.
              Inputs are individually `disabled` for now; that's the a11y-correct
              way to indicate the form isn't yet operational. */}
            <form className="space-y-4">
              <div className="space-y-2">
                <label htmlFor="email" className="text-sm font-medium">
                  E-posta
                </label>
                <Input
                  id="email"
                  type="email"
                  placeholder="ornek@cuzdan-kocu.app"
                  autoComplete="email"
                  disabled
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="password" className="text-sm font-medium">
                  Şifre
                </label>
                <Input id="password" type="password" autoComplete="current-password" disabled />
              </div>
              <Button type="button" className="w-full" disabled>
                Giriş yap 2. günde aktif
                <ArrowRight className="h-4 w-4" />
              </Button>
            </form>
            <div className="cash-envelope p-4 text-sm leading-6 text-muted-foreground">
              <p className="relative z-10">
                Henüz hesabın yok mu? Kayıt akışı 2. günde aktifleşir. Demo aile bilgileri 7. gün
                kurulum belgesinde paylaşılacak.
              </p>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
