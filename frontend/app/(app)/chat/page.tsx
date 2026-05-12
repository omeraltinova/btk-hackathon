import { MessageSquareText, ShieldCheck } from "lucide-react";

import { ChatStream } from "@/components/ChatStream";

export const metadata = {
  title: "Sohbet — Cüzdan Koçu",
};

export default function ChatPage() {
  return (
    <div className="page-enter grid min-w-0 gap-6 lg:grid-cols-[0.7fr_1.3fr]">
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

      <section className="ledger-sheet p-4 sm:p-6">
        <div className="relative z-10 space-y-5">
          <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border/80 pb-4">
            <div>
              <p className="eyebrow">Canlı koç</p>
              <h2 className="mt-2 font-display text-3xl font-black tracking-[-0.04em]">
                Cüzdan Koçu ile konuşma alanı
              </h2>
            </div>
            <span className="stamp-label bg-accent/28 text-foreground">Akış bağlı</span>
          </div>

          <ChatStream />
        </div>
      </section>
    </div>
  );
}
