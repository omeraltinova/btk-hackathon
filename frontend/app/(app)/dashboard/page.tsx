import { BellRing, CalendarDays, ReceiptText, Sparkles, WalletCards } from "lucide-react";

export const metadata = {
  title: "Panel — Cüzdan Koçu",
};

const summaryCards = [
  {
    label: "Bu ay görünür harcama",
    value: "12.450,00 ₺",
    detail: "Demo veri bağlanınca deftere yazılır",
  },
  { label: "Proaktif not", value: "1 yeni", detail: "İlk uyarı bandı 6. günde gelir" },
  { label: "Fişten kazanılan zaman", value: "10x", detail: "Manuel girişten hızlı hedef" },
] as const;

const recentItems = [
  { merchant: "Migros", category: "Market", amount: "247,50 ₺", date: "15.05.2026" },
  { merchant: "Netflix", category: "Abonelik", amount: "229,99 ₺", date: "14.05.2026" },
  { merchant: "İstanbulkart", category: "Ulaşım", amount: "150,00 ₺", date: "13.05.2026" },
] as const;

const ledgerRows = [
  { category: "Market", amount: "3.820,50 ₺", width: "78%" },
  { category: "Fatura", amount: "2.140,00 ₺", width: "54%" },
  { category: "Ulaşım", amount: "840,00 ₺", width: "32%" },
  { category: "Abonelik", amount: "459,99 ₺", width: "22%" },
] as const;

const dayPlan = [
  { day: "2. gün", title: "Giriş ve işlem ekleme", text: "E-posta, şifre ve gelir-gider akışı." },
  { day: "3. gün", title: "Koç araçları", text: "Gerçek grafikler ve veri araçları." },
  { day: "6. gün", title: "Proaktif uyarı", text: "Sormadan gelen aile bütçesi notları." },
] as const;

export default function DashboardPage() {
  return (
    <div className="page-enter space-y-8">
      <section className="grid gap-5 lg:grid-cols-[1.05fr_0.55fr] lg:items-stretch">
        <div className="ledger-sheet binder-holes p-6 pl-8 sm:p-9 sm:pl-20">
          <div className="relative z-10 max-w-3xl space-y-6">
            <span className="stamp-label bg-background/70">Proaktif aile defteri</span>
            <div className="space-y-4">
              <h1 className="font-display text-[clamp(2.5rem,6vw,5.7rem)] font-black leading-[0.92] tracking-[-0.05em]">
                Bugünkü bütçe sayfası açıldı.
              </h1>
              <p className="max-w-[62ch] text-lg leading-8 text-muted-foreground">
                Gerçek veriler bağlandığında harcama özeti, son işlemler ve aileye özel uyarılar
                burada tek bakışta, defter düzeninde okunur.
              </p>
            </div>
          </div>
        </div>

        <aside className="receipt-tape rotate-1 p-6 pt-9 text-sm leading-6 text-foreground">
          <p className="font-display text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">
            Koç notu / örnek
          </p>
          <div className="mt-5 flex items-start gap-3">
            <span className="pulse-soft grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent text-accent-foreground">
              <BellRing className="h-5 w-5" />
            </span>
            <div>
              <h2 className="font-display text-2xl font-black leading-7">
                Netflix'i gözden geçirebilirsin
              </h2>
              <p className="mt-3 text-muted-foreground">
                Kullanım sinyali zayıfsa Cüzdan Koçu bunu yargılamadan, tasarruf fırsatı olarak
                gösterecek.
              </p>
            </div>
          </div>
        </aside>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        {summaryCards.map((card, index) => (
          <div key={card.label} className="cash-envelope min-h-44 p-5">
            <div className="relative z-10 flex h-full flex-col justify-between gap-6">
              <p className="text-sm font-bold text-secondary-foreground/80">{card.label}</p>
              <div>
                <p className="font-display text-4xl font-black tabular-nums tracking-[-0.04em]">
                  {card.value}
                </p>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">{card.detail}</p>
              </div>
              <span className="font-display text-xs font-bold text-primary/70">
                ZARF {index + 1}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
        <section className="ledger-sheet p-6 sm:p-8">
          <div className="relative z-10 space-y-6">
            <div>
              <p className="eyebrow">Harcama defteri</p>
              <h2 className="mt-2 font-display text-3xl font-black tracking-[-0.04em]">
                Kategori satırları için yer hazır
              </h2>
            </div>
            <div className="space-y-4">
              {ledgerRows.map((row) => (
                <div
                  key={row.category}
                  className="grid gap-2 sm:grid-cols-[7rem_1fr_7rem] sm:items-center"
                >
                  <p className="font-semibold">{row.category}</p>
                  <div className="h-3 rounded-full bg-muted">
                    <div className="h-full rounded-full bg-primary" style={{ width: row.width }} />
                  </div>
                  <p className="font-display font-bold tabular-nums sm:text-right">{row.amount}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="space-y-3">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Son fişler</p>
              <h2 className="mt-2 font-display text-3xl font-black tracking-[-0.04em]">
                Demo akışı
              </h2>
            </div>
            <ReceiptText className="h-6 w-6 text-primary" />
          </div>
          <div className="space-y-3">
            {recentItems.map((item, index) => (
              <div
                key={`${item.merchant}-${item.date}`}
                className="receipt-tape flex items-center justify-between gap-4 px-5 py-6 transition-transform duration-300 ease-quint motion-safe:hover:-rotate-1"
              >
                <div>
                  <p className="font-display text-lg font-black">{item.merchant}</p>
                  <p className="text-sm text-muted-foreground">
                    {item.category} / {item.date}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-display text-xl font-black tabular-nums">{item.amount}</p>
                  <p className="text-xs font-bold text-muted-foreground">SIRA {index + 1}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="grid gap-3 md:grid-cols-3">
        {dayPlan.map((item, index) => {
          const Icon = index === 0 ? CalendarDays : index === 1 ? WalletCards : Sparkles;
          return (
            <div key={item.day} className="tab-chip hard-shadow-primary bg-card/90 p-5 pr-8">
              <Icon className="h-5 w-5 text-primary" />
              <p className="mt-5 font-display text-xl font-black">{item.day}</p>
              <p className="mt-1 font-semibold">{item.title}</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.text}</p>
            </div>
          );
        })}
      </section>
    </div>
  );
}
