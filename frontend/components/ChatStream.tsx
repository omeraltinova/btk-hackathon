"use client";

import { Bot, Send } from "lucide-react";
import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type ChatDraftMessage = {
  id: string;
  role: "user" | "coach";
  text: string;
};

export function ChatStream() {
  const [messages, setMessages] = useState<ChatDraftMessage[]>([]);
  const [draft, setDraft] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", text },
      {
        id: crypto.randomUUID(),
        role: "coach",
        text: "Canlı koç bağlantısı 3. günde eklenecek. Bu alanda şu an finansal veri üretilmiyor.",
      },
    ]);
    setDraft("");
  }

  return (
    <div className="space-y-5">
      <div className="min-h-72 space-y-4">
        {messages.length === 0 ? (
          <div className="receipt-tape px-5 py-8">
            <Bot className="h-6 w-6 text-primary" />
            <h3 className="mt-4 font-display text-2xl font-black">Sohbet alanı hazır</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Burada örnek finansal cevap gösterilmiyor. Mesaj yazdığında sadece yerel taslak akışı
              görünür; gerçek koç ve araç izleri Day 3'te backend'e bağlanacak.
            </p>
          </div>
        ) : (
          messages.map((message) => {
            const isCoach = message.role === "coach";
            return (
              <div
                key={message.id}
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
                  <p className="font-semibold">{isCoach ? "Cüzdan Koçu" : "Sen"}</p>
                  <p className="mt-1 opacity-80">{message.text}</p>
                </div>
              </div>
            );
          })
        )}
      </div>

      <div className="cash-envelope p-4">
        <div className="relative z-10 text-sm font-bold">Araç izi</div>
        <p className="relative z-10 mt-2 text-sm leading-6 text-muted-foreground">
          Canlı backend akışı bağlandığında kullanılan araçlar burada görünecek.
        </p>
      </div>

      <form
        className="flex gap-2 rounded-[1.75rem] border border-border/70 bg-muted/50 p-2"
        onSubmit={handleSubmit}
      >
        <Input
          placeholder="Koça sormak istediğini yaz"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
        />
        <Button type="submit" aria-label="Mesaj gönder">
          <Send className="h-4 w-4" />
        </Button>
      </form>
    </div>
  );
}
