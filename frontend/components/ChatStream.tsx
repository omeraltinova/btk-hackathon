"use client";

import { Bot, Loader2, Send, Wrench } from "lucide-react";
import { type FormEvent, useRef, useState } from "react";

import { ChatMessage } from "@/components/ChatMessage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { streamChat } from "@/lib/sse";
import type { ChatStreamEvent, ChatToolPayload } from "@/lib/types";

type ChatMessageItem = {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
};

type ToolTraceItem = {
  id: string;
  name: string;
  status: "running" | "done";
  detail: string;
};

function describeToolInput(input: ChatToolPayload): string {
  if ("category" in input || "days" in input) {
    const category = typeof input.category === "string" ? input.category : "Tüm kategoriler";
    const days = typeof input.days === "number" ? input.days : 30;
    return `${category} / son ${days} gün`;
  }
  if ("only_active" in input) return "Aktif kayıtlar";
  return "Güvenli oturum kapsamı";
}

function describeToolResult(event: Extract<ChatStreamEvent, { type: "tool_result" }>): string {
  const result = event.result;
  if (event.tool_name === "get_spending") {
    const total =
      typeof result.total_amount_formatted === "string" ? result.total_amount_formatted : "0,00 ₺";
    const count = typeof result.transaction_count === "number" ? result.transaction_count : 0;
    return `${total} / ${count} işlem`;
  }
  if (event.tool_name === "get_subscriptions") {
    const total =
      typeof result.monthly_total_formatted === "string"
        ? result.monthly_total_formatted
        : "0,00 ₺";
    const count = typeof result.count === "number" ? result.count : 0;
    return `${total} aylık etki / ${count} kayıt`;
  }
  return "Sonuç alındı";
}

export function ChatStream() {
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [toolTrace, setToolTrace] = useState<ToolTraceItem[]>([]);
  const [draft, setDraft] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  function applyStreamEvent(event: ChatStreamEvent, assistantId: string) {
    if (event.type === "message_start") {
      setConversationId(event.conversation_id);
      return;
    }
    if (event.type === "tool_call") {
      setToolTrace((current) => [
        {
          id: crypto.randomUUID(),
          name: event.tool_name,
          status: "running",
          detail: describeToolInput(event.input),
        },
        ...current,
      ]);
      return;
    }
    if (event.type === "tool_result") {
      setToolTrace((current) => {
        const index = current.findIndex(
          (item) => item.name === event.tool_name && item.status === "running",
        );
        if (index === -1) {
          return [
            {
              id: crypto.randomUUID(),
              name: event.tool_name,
              status: "done",
              detail: describeToolResult(event),
            },
            ...current,
          ];
        }
        return current.map((item, itemIndex) =>
          itemIndex === index
            ? { ...item, status: "done", detail: describeToolResult(event) }
            : item,
        );
      });
      return;
    }
    if (event.type === "delta") {
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? { ...message, content: `${message.content}${event.content}` }
            : message,
        ),
      );
      return;
    }
    if (event.type === "done") {
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId ? { ...message, isStreaming: false } : message,
        ),
      );
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || isStreaming) return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const assistantId = crypto.randomUUID();

    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "user", content: text },
      { id: assistantId, role: "assistant", content: "", isStreaming: true },
    ]);
    setDraft("");
    setIsStreaming(true);

    try {
      await streamChat(
        { message: text, conversation_id: conversationId },
        (streamEvent) => applyStreamEvent(streamEvent, assistantId),
        { signal: controller.signal },
      );
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      const message = err instanceof Error ? err.message : "Koç akışı kesildi, tekrar dener misin?";
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantId ? { ...item, content: message, isStreaming: false } : item,
        ),
      );
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="min-h-72 space-y-4">
        {messages.length === 0 ? (
          <div className="receipt-tape px-5 py-8">
            <Bot className="h-6 w-6 text-primary" />
            <h3 className="mt-4 font-display text-2xl font-black">Koç akışı hazır</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Harcama veya abonelik sorusu yazdığında Cüzdan Koçu güvenli oturum verinle araç
              çağırır ve yanıtı parça parça gösterir.
            </p>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage
              key={message.id}
              role={message.role}
              content={message.content}
              isStreaming={message.isStreaming}
            />
          ))
        )}
      </div>

      <div className="cash-envelope p-4">
        <div className="relative z-10 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-bold">
            <Wrench className="h-4 w-4" />
            Araç izi
          </div>
          {isStreaming ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : null}
        </div>
        {toolTrace.length === 0 ? (
          <p className="relative z-10 mt-2 text-sm leading-6 text-muted-foreground">
            İlk araç çağrısı burada görünecek.
          </p>
        ) : (
          <div className="relative z-10 mt-3 space-y-2">
            {toolTrace.slice(0, 4).map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between gap-3 rounded-2xl bg-background/65 px-3 py-2 text-xs"
              >
                <span className="font-bold">{item.name}</span>
                <span className="text-right text-muted-foreground">{item.detail}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <form
        className="flex gap-2 rounded-[1.75rem] border border-border/70 bg-muted/50 p-2"
        onSubmit={handleSubmit}
      >
        <Input
          placeholder="Bu ay markete ne kadar harcadım?"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={isStreaming}
        />
        <Button type="submit" aria-label="Mesaj gönder" disabled={isStreaming || !draft.trim()}>
          {isStreaming ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </Button>
      </form>
    </div>
  );
}
