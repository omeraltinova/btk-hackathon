"use client";

import { Bot, ImagePlus, Loader2, Send, Wrench, X } from "lucide-react";
import { type ChangeEvent, type FormEvent, useRef, useState } from "react";

import { ChatChart } from "@/components/ChatChart";
import { ChatMessage } from "@/components/ChatMessage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { amountToKurus, formatKurus } from "@/lib/format";
import { useKidMode } from "@/lib/kid-mode";
import { streamChat } from "@/lib/sse";
import type { ChatChartSpec, ChatStreamEvent, ChatToolPayload } from "@/lib/types";

type ChatMessageItem = {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  attachments?: ChatAttachmentItem[];
};

type ToolTraceItem = {
  id: string;
  name: string;
  status: "running" | "done";
  detail: string;
};

type ReceiptAttachment = {
  filename: string;
  contentType: string;
  base64: string;
};

type ChatAttachmentItem =
  | {
      id: string;
      type: "chart";
      spec: ChatChartSpec;
    }
  | {
      id: string;
      type: "image";
      imageUrl: string;
      altText: string;
    };

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function extractChart(result: ChatToolPayload): ChatChartSpec | null {
  const candidate = (result as Record<string, unknown>).chart;
  if (!isRecord(candidate)) return null;
  const type = candidate.type === "pie" ? "pie" : candidate.type === "bar" ? "bar" : null;
  if (!type) return null;
  if (typeof candidate.title !== "string") return null;
  if (!Array.isArray(candidate.data)) return null;
  const points: ChatChartSpec["data"] = [];
  for (const entry of candidate.data) {
    if (!isRecord(entry)) continue;
    const label = typeof entry.label === "string" ? entry.label : null;
    const rawValue = entry.value;
    const value =
      typeof rawValue === "number"
        ? rawValue
        : typeof rawValue === "string"
          ? Number(rawValue)
          : null;
    const valueFormatted = typeof entry.value_formatted === "string" ? entry.value_formatted : null;
    if (label === null || value === null || !Number.isFinite(value) || valueFormatted === null) {
      continue;
    }
    points.push({ label, value, value_formatted: valueFormatted });
  }
  if (points.length === 0) return null;
  return {
    type,
    title: candidate.title,
    subtitle: typeof candidate.subtitle === "string" ? candidate.subtitle : null,
    data: points,
    value_label: typeof candidate.value_label === "string" ? candidate.value_label : null,
    currency: typeof candidate.currency === "string" ? candidate.currency : null,
  };
}

function describeToolInput(input: ChatToolPayload): string {
  if ("chart_type" in input) {
    const chartType = input.chart_type === "pie" ? "Pasta grafik" : "Çubuk grafik";
    const days = typeof input.days === "number" ? input.days : 30;
    return `${chartType} / son ${days} gün`;
  }
  if ("category" in input || "days" in input) {
    const category = typeof input.category === "string" ? input.category : "Tüm kategoriler";
    const days = typeof input.days === "number" ? input.days : 30;
    return `${category} / son ${days} gün`;
  }
  if ("only_active" in input) return "Aktif kayıtlar";
  if ("filename" in input) return String(input.filename);
  if ("concept" in input) return String(input.concept);
  if ("scenario" in input) return "Senaryo simülasyonu";
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
  if (event.tool_name === "analyze_receipt") {
    const merchant = typeof result.merchant === "string" ? result.merchant : "Fiş";
    const amount = typeof result.amount === "string" ? result.amount : "";
    return amount ? `${merchant} / ${formatKurus(amountToKurus(amount))}` : merchant;
  }
  if (event.tool_name === "explain_concept") return "Çocuk dostu açıklama";
  if (event.tool_name === "simulate_scenario") return "Simülasyon hazır";
  if (event.tool_name === "visualize_spending") {
    const total =
      typeof result.total_amount_formatted === "string" ? result.total_amount_formatted : "0,00 ₺";
    return `Grafik hazır / ${total}`;
  }
  if (event.tool_name === "get_user_memory") {
    const count = typeof result.count === "number" ? result.count : 0;
    return `${count} hafıza kaydı`;
  }
  if (event.tool_name === "illustrate_concept") {
    return typeof result.image_url === "string" ? "Görsel hazır" : "Görsel hazırlanamadı";
  }
  return "Sonuç alındı";
}

function renderAttachment(attachment: ChatAttachmentItem) {
  if (attachment.type === "chart") {
    return <ChatChart key={attachment.id} spec={attachment.spec} />;
  }
  return (
    <figure
      key={attachment.id}
      className="overflow-hidden rounded-3xl border border-border/70 bg-card/85 shadow-sm"
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- Backend returns user-scoped MinIO URLs from runtime config. */}
      <img src={attachment.imageUrl} alt={attachment.altText} className="w-full object-cover" />
      <figcaption className="px-4 py-3 text-xs font-medium text-muted-foreground">
        {attachment.altText}
      </figcaption>
    </figure>
  );
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = reader.result;
      if (typeof value !== "string") {
        reject(new Error("Fiş görseli okunamadı."));
        return;
      }
      resolve(value.split(",")[1] ?? "");
    };
    reader.onerror = () => reject(new Error("Fiş görseli okunamadı."));
    reader.readAsDataURL(file);
  });
}

export function ChatStream() {
  const { isKid } = useKidMode();
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [toolTrace, setToolTrace] = useState<ToolTraceItem[]>([]);
  const [draft, setDraft] = useState("");
  const [attachment, setAttachment] = useState<ReceiptAttachment | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
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
      const chart = extractChart(event.result);
      if (chart) {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  attachments: [
                    ...(message.attachments ?? []),
                    { id: crypto.randomUUID(), type: "chart", spec: chart },
                  ],
                }
              : message,
          ),
        );
      }
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
    if (event.type === "image") {
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                attachments: [
                  ...(message.attachments ?? []),
                  {
                    id: crypto.randomUUID(),
                    type: "image",
                    imageUrl: event.image_url,
                    altText: event.alt_text,
                  },
                ],
              }
            : message,
        ),
      );
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
    setAttachment(null);
    setFileError(null);
    setIsStreaming(true);

    try {
      await streamChat(
        {
          message: text,
          conversation_id: conversationId,
          receipt_image_base64: attachment?.base64 ?? null,
          receipt_filename: attachment?.filename ?? null,
          receipt_content_type: attachment?.contentType ?? null,
        },
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

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setFileError("Sohbete yalnızca JPG, PNG veya WEBP fişi ekleyebilirsin.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setFileError("Fiş dosyası en fazla 5 MB olmalı.");
      return;
    }
    try {
      const base64 = await readFileAsBase64(file);
      setAttachment({ filename: file.name, contentType: file.type, base64 });
      setFileError(null);
      if (!draft.trim()) setDraft("Bu fişi analiz eder misin?");
    } catch (err) {
      setFileError(err instanceof Error ? err.message : "Fiş görseli okunamadı.");
    }
  }

  return (
    <div className="space-y-5">
      <div className="min-h-72 space-y-4">
        {messages.length === 0 ? (
          <div className="receipt-tape px-5 py-8">
            <Bot className="h-6 w-6 text-primary" />
            <h3 className="mt-4 font-display text-2xl font-black">
              {isKid ? "Koçun seni dinliyor" : "Koç akışı hazır"}
            </h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {isKid
                ? "Harçlığın, kumbaran veya merak ettiğin bir şey hakkında soru sorabilirsin. Örneğin: 'Faiz nedir?' ya da 'Harçlığımı nasıl biriktiririm?'"
                : "Harcama veya abonelik sorusu yazdığında Cüzdan Koçu güvenli oturum verinle araç çağırır. Fiş görseli eklersen fiş analiz aracı da aynı akışta görünür."}
            </p>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage
              key={message.id}
              role={message.role}
              content={message.content}
              isStreaming={message.isStreaming}
            >
              {message.attachments?.map(renderAttachment)}
            </ChatMessage>
          ))
        )}
      </div>

      {isKid ? null : (
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
                  className="flex flex-col gap-1 rounded-2xl bg-background/65 px-3 py-2 text-xs sm:flex-row sm:items-center sm:justify-between sm:gap-3"
                >
                  <span className="font-bold">{item.name}</span>
                  <span className="break-words text-muted-foreground sm:text-right">
                    {item.detail}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <form
        className="bg-muted/62 space-y-2 rounded-[1.75rem] border border-border/70 p-2"
        onSubmit={handleSubmit}
      >
        {attachment || fileError ? (
          <div className="flex flex-wrap items-center gap-2 px-2">
            {attachment ? (
              <span className="stamp-label max-w-full bg-background/70 text-muted-foreground">
                <ImagePlus className="h-3.5 w-3.5" />
                <span className="max-w-[12rem] truncate sm:max-w-[20rem]">
                  {attachment.filename}
                </span>
                <button
                  type="button"
                  aria-label="Fişi kaldır"
                  onClick={() => setAttachment(null)}
                  className="ml-1 rounded-full p-0.5 hover:bg-muted"
                >
                  <X className="h-3 w-3" />
                </button>
              </span>
            ) : null}
            {fileError ? (
              <span className="bg-destructive/14 rounded-full px-3 py-1 text-xs font-semibold text-foreground">
                {fileError}
              </span>
            ) : null}
          </div>
        ) : null}
        <div className="grid grid-cols-[2.75rem_minmax(0,1fr)_2.75rem] gap-2">
          <label className="inline-flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border border-border bg-background/70 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground">
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              className="sr-only"
              disabled={isStreaming}
              onChange={handleFileChange}
            />
            <ImagePlus className="h-4 w-4" />
            <span className="sr-only">Fiş ekle</span>
          </label>
          <Input
            placeholder={
              isKid
                ? "Faiz nedir? Harçlığımı nasıl biriktiririm?"
                : "Bu ay markete ne kadar harcadım?"
            }
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={isStreaming}
          />
          <Button
            type="submit"
            className="min-h-11"
            aria-label="Mesaj gönder"
            disabled={isStreaming || !draft.trim()}
          >
            {isStreaming ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </form>
    </div>
  );
}
