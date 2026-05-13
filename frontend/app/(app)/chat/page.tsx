import { ChatHero } from "@/components/ChatHero";
import { ChatStream } from "@/components/ChatStream";

export const metadata = {
  title: "Sohbet — Cüzdan Koçu",
};

export default function ChatPage() {
  return (
    <div className="page-enter grid min-w-0 gap-6 lg:grid-cols-[0.7fr_1.3fr]">
      <ChatHero />

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
