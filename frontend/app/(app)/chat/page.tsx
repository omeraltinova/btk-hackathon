import { History } from "lucide-react";
import Link from "next/link";

import { ChatHero } from "@/components/ChatHero";
import { ChatStream } from "@/components/ChatStream";
import { Button } from "@/components/ui/button";

export const metadata = {
  title: "Sohbet — Cüzdan Koçu",
};

export default function ChatPage() {
  return (
    <div className="page-enter flex h-[calc(100svh-9.5rem)] min-h-0 min-w-0 flex-col gap-3 overflow-hidden sm:h-[calc(100svh-8.5rem)] lg:h-[calc(100svh-8rem)]">
      <ChatHero />

      <section className="ledger-sheet flex min-h-0 flex-1 p-3 sm:p-4">
        <div className="relative z-10 flex min-h-0 w-full flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/80 pb-3">
            <div>
              <p className="eyebrow">Canlı koç</p>
              <h2 className="mt-1 font-display text-2xl font-black tracking-[-0.04em] sm:text-3xl">
                Konuşma masası
              </h2>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button asChild variant="outline" size="sm">
                <Link href="/chat/history">
                  <History className="h-4 w-4" />
                  Sohbet geçmişi
                </Link>
              </Button>
              <span className="stamp-label bg-accent/28 text-foreground">Akış bağlı</span>
            </div>
          </div>

          <div className="min-h-0 flex-1">
            <ChatStream />
          </div>
        </div>
      </section>
    </div>
  );
}
