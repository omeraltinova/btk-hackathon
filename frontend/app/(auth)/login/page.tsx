import { LockKeyhole, ShieldCheck, Sparkles, Wallet } from "lucide-react";

import { LoginForm } from "@/components/auth/login-form";

export const metadata = {
  title: "Giriş — Cüzdan Koçu",
};

export default function LoginPage() {
  return (
    <div className="relative grid min-h-screen place-items-center overflow-x-hidden p-4 sm:p-6 xl:p-8">
      <div className="page-enter grid w-full max-w-[94rem] gap-6 xl:grid-cols-[minmax(31rem,0.85fr)_minmax(41rem,1.15fr)] xl:items-center xl:gap-8 2xl:gap-10">
        <div className="flex justify-center xl:hidden">
          <span className="stamp-label bg-background/70 text-primary">
            <Wallet className="h-3.5 w-3.5" />
            Cüzdan Koçu
          </span>
        </div>
        <section className="ledger-sheet binder-holes hidden min-h-[640px] p-8 pl-16 xl:block 2xl:pl-20">
          <div className="relative z-10 flex min-h-[570px] flex-col justify-between">
            <div>
              <span className="stamp-label bg-background/70">
                <Wallet className="h-3.5 w-3.5" />
                Cüzdan Koçu
              </span>
            </div>

            <div className="max-w-[31rem] space-y-5">
              <p className="eyebrow">Sıfırdan 60 saniyeye</p>
              <h1 className="break-words font-display text-[clamp(2.45rem,3.5vw,3.65rem)] font-black leading-[0.9] tracking-[-0.05em]">
                Bütçe takibini aile sohbetine yaklaştırıyoruz.
              </h1>
              <p className="text-foreground/78 text-lg leading-8">
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

        <section className="receipt-tape w-full min-w-0 p-5 pt-9 sm:p-6 sm:pt-10 xl:p-8 xl:pt-12">
          <div className="space-y-6">
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

            <LoginForm />
          </div>
        </section>
      </div>
    </div>
  );
}
