import { Bot, MessageSquareText, Send, ShieldCheck, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export const metadata = {
  title: "Sohbet — Cüzdan Koçu",
};

const mockMessages = [
  {
    role: "Ayşe",
    text: "Bu ay markete ne kadar harcadık?",
  },
  {
    role: "Cüzdan Koçu",
    text: "3. günde gerçek veriden hesaplayacağım. Şimdilik akış hazır: önce harcama aracı çağrılır, sonra tutar Türkçe formatta açıklanır.",
  },
] as const;

const promptChips = ["Aboneliklerimi göster", "Faiz nedir?", "Fiş eklemek istiyorum"] as const;

export default function ChatPage() {
  return (
    <div className="page-enter grid gap-6 lg:grid-cols-[0.7fr_1.3fr]">
      <section className="ledger-sheet binder-holes p-6 pl-8 sm:p-8 sm:pl-16">
        <div className="relative z-10 space-y-7">
          <span className="stamp-label bg-background/70">
            <MessageSquareText className="h-3.5 w-3.5" />
            Koç modu
          </span>
          <div className="space-y-3">
            <h1 className="font-display text-5xl font-black leading-[0.95] tracking-[-0.05em]">
              Sohbet sayfası, cevap kadar kanıt da gösterir.
            </h1>
            <p className="max-w-[58ch] text-base leading-7 text-muted-foreground">
              Akışlı cevaplar 3. günde bağlandığında araç çağrıları görünür olacak; kullanıcı hangi
              veriye dayanarak cevap aldığını anlayacak.
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

      <section className="ledger-sheet p-4 sm:p-6">
        <div className="relative z-10 space-y-5">
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border/80 pb-4">
            <div>
              <p className="eyebrow">1. gün konuşma defteri</p>
              <h2 className="mt-2 font-display text-3xl font-black tracking-[-0.04em]">
                Cüzdan Koçu ile konuşma alanı
              </h2>
            </div>
            <span className="stamp-label bg-accent/25 text-accent-foreground">Önizleme</span>
          </div>

          <div className="space-y-4">
            {mockMessages.map((message) => {
              const isCoach = message.role === "Cüzdan Koçu";
              return (
                <div
                  key={message.role}
                  className={`flex gap-3 ${isCoach ? "justify-start" : "justify-end"}`}
                >
                  {isCoach ? (
                    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[1rem_1rem_0.5rem_1rem] bg-primary text-primary-foreground">
                      <Bot className="h-4 w-4" />
                    </span>
                  ) : null}
                  <div
                    className={`max-w-[78%] px-4 py-3 text-sm leading-6 ${
                      isCoach
                        ? "receipt-tape rotate-[-0.5deg] text-foreground"
                        : "hard-shadow-accent rounded-[1.4rem_1.4rem_0.65rem_1.4rem] bg-primary text-primary-foreground"
                    }`}
                  >
                    <p className="font-semibold">{message.role}</p>
                    <p className="mt-1 opacity-80">{message.text}</p>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="cash-envelope p-4">
            <div className="relative z-10 flex items-center gap-2 text-sm font-bold">
              <Sparkles className="h-4 w-4 text-primary" />
              Araç izi
            </div>
            <div className="relative z-10 mt-3 flex flex-wrap gap-2 text-xs">
              <span className="stamp-label bg-background/65 normal-case tracking-normal text-secondary-foreground">
                harcama_ozeti(kategori=market, gun=30)
              </span>
              <span className="rounded-full border border-border/70 px-3 py-1.5 text-muted-foreground">
                3. günde canlı
              </span>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {promptChips.map((chip) => (
              <button
                key={chip}
                type="button"
                className="rounded-full border border-border/70 bg-background/70 px-3 py-2 text-sm font-semibold text-muted-foreground transition-colors hover:bg-accent/40 hover:text-accent-foreground"
              >
                {chip}
              </button>
            ))}
          </div>

          <div className="flex gap-2 rounded-[1.75rem] border border-border/70 bg-muted/50 p-2">
            <Input placeholder="2. günde mesaj yazabileceksin" disabled />
            <Button type="button" disabled aria-label="Mesaj gönder">
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
