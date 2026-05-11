import { Baby, GraduationCap, ShieldCheck, UserRound, Users } from "lucide-react";

export const metadata = {
  title: "Aile — Cüzdan Koçu",
};

const familyMembers = [
  { name: "Ayşe Yılmaz", role: "Ebeveyn", detail: "Aile bütçesini yönetir", icon: UserRound },
  { name: "Mehmet Yılmaz", role: "Ebeveyn", detail: "Abonelikleri takip eder", icon: Users },
  { name: "Elif Yılmaz", role: "Çocuk", detail: "Harçlık koçu modu", icon: Baby },
] as const;

export default function FamilyPage() {
  return (
    <div className="page-enter space-y-8">
      <section className="grid gap-5 lg:grid-cols-[1fr_0.55fr] lg:items-stretch">
        <div className="ledger-sheet binder-holes p-6 pl-8 sm:p-9 sm:pl-20">
          <div className="relative z-10 max-w-3xl space-y-5">
            <span className="stamp-label bg-background/70">Aile modu</span>
            <h1 className="font-display text-[clamp(2.4rem,5.6vw,5.3rem)] font-black leading-[0.94] tracking-[-0.05em]">
              Aynı evde farklı finans dili.
            </h1>
            <p className="max-w-[62ch] text-lg leading-8 text-muted-foreground">
              Ebeveyn tüm aileyi görür; çocuk sadece kendi verisini görür. 5. günde aile geçişi ve
              çocuk dostu koç modu buraya bağlanır.
            </p>
          </div>
        </div>

        <aside className="receipt-tape rotate-1 p-6 pt-9">
          <div className="flex items-center gap-3">
            <ShieldCheck className="h-6 w-6 text-primary" />
            <div>
              <p className="font-display text-2xl font-black">Veri sınırı görünür</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                İK-4 ve İK-5 tasarımda da korunur.
              </p>
            </div>
          </div>
        </aside>
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        {familyMembers.map((member, index) => {
          const Icon = member.icon;
          return (
            <article key={member.name} className="cash-envelope min-h-52 p-5">
              <div className="relative z-10 flex h-full flex-col justify-between gap-5">
                <div className="flex items-start justify-between gap-4">
                  <Icon className="h-6 w-6 text-primary" />
                  <span className="stamp-label bg-background/70 text-accent-foreground">
                    {member.role}
                  </span>
                </div>
                <div>
                  <p className="font-display text-3xl font-black tracking-[-0.04em]">
                    {member.name}
                  </p>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">{member.detail}</p>
                </div>
                <p className="font-display text-xs font-bold text-primary/70">
                  AİLE KAYDI {index + 1}
                </p>
              </div>
            </article>
          );
        })}
      </section>

      <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
        <section className="ledger-sheet p-6 sm:p-8">
          <div className="relative z-10 space-y-5">
            <span className="stamp-label bg-background/70">Çocuk modu</span>
            <div>
              <p className="font-display text-3xl font-black tracking-[-0.04em]">Faiz nedir?</p>
              <p className="mt-4 max-w-[58ch] text-base leading-8 text-muted-foreground">
                Diyelim kumbarana 100 ₺ koydun. Banka, paran orada durduğu için her ay küçük bir
                teşekkür parası ekler. Bu ekstra paraya faiz denir.
              </p>
            </div>
          </div>
        </section>

        <section className="space-y-4">
          <div>
            <p className="eyebrow">5. gün hedefi</p>
            <h2 className="mt-2 font-display text-3xl font-black tracking-[-0.04em]">
              Aile geçişi akışı
            </h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {["Ebeveyn giriş yapar", "Elif profiline geçer", "Yeni oturum çocuk rolünü taşır"].map(
              (item, index) => (
                <div key={item} className="receipt-tape px-5 py-7">
                  <span className="font-display text-3xl font-black text-primary">{index + 1}</span>
                  <p className="mt-4 text-sm font-bold leading-6">{item}</p>
                </div>
              ),
            )}
          </div>
        </section>
      </div>

      <div className="tab-chip hard-shadow-primary bg-card/90 p-5 pr-8">
        <div className="flex items-center gap-3">
          <GraduationCap className="h-5 w-5 text-primary" />
          <p className="font-semibold">Aile sekmesi bireysel kullanıcılarda gizlenecek.</p>
        </div>
      </div>
    </div>
  );
}
