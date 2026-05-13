"use client";

import {
  Bot,
  ImagePlus,
  Loader2,
  MessageSquareText,
  Plus,
  Send,
  Sparkles,
  Wrench,
  X,
} from "lucide-react";
import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";

import { ChatChart } from "@/components/ChatChart";
import { ChatMessage } from "@/components/ChatMessage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ACTIVE_PROFILE_EVENT } from "@/lib/active-profile";
import { api, ApiError } from "@/lib/api";
import {
  chatAttachmentsFromHistory,
  extractChart,
  type ChatAttachmentItem,
} from "@/lib/chat-attachments";
import { readActiveConversationId, rememberActiveConversationId } from "@/lib/chat-session";
import { amountToKurus, formatKurus } from "@/lib/format";
import { useKidMode } from "@/lib/kid-mode";
import { streamChat } from "@/lib/sse";
import type {
  ChatStreamEvent,
  ChatToolPayload,
  ConversationListItem,
  ConversationMessages,
} from "@/lib/types";
import { cn } from "@/lib/utils";

type ChatMessageItem = {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  attachments?: ChatAttachmentItem[];
};

type ChatPanel = "chat" | "tools";

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

const ADULT_SUGGESTIONS = [
  "Bu ay markete ne kadar harcadım?",
  "Harcamalarımı grafik olarak gösterir misin?",
  "Aktif aboneliklerimi özetler misin?",
  "Kredi kartı asgarisini ödersem ne olur?",
  "Enflasyonu aile bütçesiyle açıklar mısın?",
] as const;

const KID_SUGGESTIONS = [
  "Harçlığımı nasıl biriktiririm?",
  "Faiz nedir, kumbarayla anlatır mısın?",
  "Bu ay nereye para harcamışım?",
  "Bayram paramı nasıl saklamalıyım?",
] as const;

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

function friendlyError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

function messagesFromThread(thread: ConversationMessages): ChatMessageItem[] {
  const pendingAttachments: ChatAttachmentItem[] = [];
  return thread.messages.flatMap((message) => {
    const attachments = chatAttachmentsFromHistory(message.attachments).map((attachment) => ({
      ...attachment,
      id: `${message.id}-${attachment.id}`,
    }));
    if (message.role === "tool") {
      pendingAttachments.push(...attachments);
      return [];
    }
    if (message.role !== "user" && message.role !== "assistant") return [];
    const messageAttachments = message.role === "assistant" ? pendingAttachments.splice(0) : [];
    messageAttachments.push(...attachments);
    return [
      {
        id: message.id,
        role: message.role,
        content: message.content,
        attachments: messageAttachments.length > 0 ? messageAttachments : undefined,
      },
    ];
  });
}

export function ChatStream() {
  const { isKid } = useKidMode();
  const [messages, setMessages] = useState<ChatMessageItem[]>([]);
  const [toolTrace, setToolTrace] = useState<ToolTraceItem[]>([]);
  const [activePanel, setActivePanel] = useState<ChatPanel>("chat");
  const [draft, setDraft] = useState("");
  const [attachment, setAttachment] = useState<ReceiptAttachment | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [suggestionIndex, setSuggestionIndex] = useState(0);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isHydrating, setIsHydrating] = useState(true);
  const [fileError, setFileError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const suggestions = isKid ? KID_SUGGESTIONS : ADULT_SUGGESTIONS;
  const activeSuggestion =
    suggestions[suggestionIndex % suggestions.length] ?? ADULT_SUGGESTIONS[0];

  useEffect(() => {
    let cancelled = false;

    async function loadConversation() {
      setIsHydrating(true);
      setHistoryError(null);
      try {
        let targetId = readActiveConversationId();
        if (!targetId) {
          const conversations = await api<ConversationListItem[]>("/api/conversations?limit=1", {
            silent: true,
          });
          targetId = conversations[0]?.id ?? null;
        }

        if (!targetId) {
          if (!cancelled) {
            setConversationId(null);
            setMessages([]);
            setToolTrace([]);
            rememberActiveConversationId(null);
          }
          return;
        }

        const thread = await api<ConversationMessages>(`/api/conversations/${targetId}/messages`, {
          silent: true,
        });
        if (cancelled) return;
        setConversationId(thread.conversation_id);
        setMessages(messagesFromThread(thread));
        setToolTrace([]);
        rememberActiveConversationId(thread.conversation_id);
      } catch (err) {
        if (!cancelled) {
          setConversationId(null);
          setMessages([]);
          setToolTrace([]);
          rememberActiveConversationId(null);
          setHistoryError(friendlyError(err, "Son sohbetin yüklenemedi."));
        }
      } finally {
        if (!cancelled) setIsHydrating(false);
      }
    }

    void loadConversation();
    function reloadForProfile() {
      rememberActiveConversationId(null);
      void loadConversation();
    }
    window.addEventListener(ACTIVE_PROFILE_EVENT, reloadForProfile);
    return () => {
      cancelled = true;
      window.removeEventListener(ACTIVE_PROFILE_EVENT, reloadForProfile);
    };
  }, []);

  useEffect(() => {
    if (activePanel !== "chat") return;
    const node = scrollRef.current;
    if (!node) return;
    node.scrollTo({ top: node.scrollHeight, behavior: isStreaming ? "auto" : "smooth" });
  }, [activePanel, isStreaming, messages]);

  useEffect(() => {
    if (isKid && activePanel === "tools") setActivePanel("chat");
  }, [activePanel, isKid]);

  useEffect(() => {
    setSuggestionIndex(0);
    const intervalId = window.setInterval(() => {
      setSuggestionIndex((current) => current + 1);
    }, 4200);
    return () => window.clearInterval(intervalId);
  }, [isKid]);

  function applyStreamEvent(event: ChatStreamEvent, assistantId: string) {
    if (event.type === "message_start") {
      setConversationId(event.conversation_id);
      rememberActiveConversationId(event.conversation_id);
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
    if (!text || isStreaming || isHydrating) return;

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
    setHistoryError(null);
    setActivePanel("chat");
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

  function handleNewConversation() {
    if (isStreaming || isHydrating) return;
    abortRef.current?.abort();
    setConversationId(null);
    setMessages([]);
    setToolTrace([]);
    setAttachment(null);
    setFileError(null);
    setHistoryError(null);
    setDraft("");
    setActivePanel("chat");
    rememberActiveConversationId(null);
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div
          role="tablist"
          aria-label="Sohbet çalışma alanı"
          className="inline-flex rounded-[1.25rem] border border-border/70 bg-card/80 p-1 shadow-sm"
        >
          <button
            type="button"
            role="tab"
            aria-selected={activePanel === "chat"}
            aria-controls="chat-panel"
            onClick={() => setActivePanel("chat")}
            className={cn(
              "inline-flex items-center gap-2 rounded-[1rem] px-3 py-2 text-sm font-bold transition-colors",
              activePanel === "chat"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted/70 hover:text-foreground",
            )}
          >
            <MessageSquareText className="h-4 w-4" />
            Sohbet
          </button>
          {isKid ? null : (
            <button
              type="button"
              role="tab"
              aria-selected={activePanel === "tools"}
              aria-controls="tools-panel"
              onClick={() => setActivePanel("tools")}
              className={cn(
                "inline-flex items-center gap-2 rounded-[1rem] px-3 py-2 text-sm font-bold transition-colors",
                activePanel === "tools"
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted/70 hover:text-foreground",
              )}
            >
              <Wrench className="h-4 w-4" />
              Araç izi
              {toolTrace.length > 0 ? (
                <span className="rounded-full bg-background/85 px-1.5 py-0.5 text-[0.68rem] text-foreground">
                  {toolTrace.length}
                </span>
              ) : null}
            </button>
          )}
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={handleNewConversation}
          disabled={isStreaming || isHydrating}
          className="rounded-[1rem]"
        >
          <Plus className="h-4 w-4" />
          Yeni sohbet
        </Button>
      </div>

      {historyError ? (
        <p className="bg-destructive/14 rounded-2xl border border-destructive/35 px-4 py-2 text-sm font-semibold text-foreground">
          {historyError}
        </p>
      ) : null}

      <div className="bg-background/58 min-h-0 flex-1 overflow-hidden rounded-[1.75rem] border border-border/70">
        {activePanel === "chat" ? (
          <div
            id="chat-panel"
            role="tabpanel"
            ref={scrollRef}
            className="h-full overflow-y-auto px-3 py-3 sm:px-4 sm:py-4"
          >
            <div className="space-y-4">
              {isHydrating ? (
                <div className="receipt-tape flex items-center gap-2 px-5 py-6 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Son sohbet yükleniyor...
                </div>
              ) : messages.length === 0 ? (
                <div className="receipt-tape px-5 py-7">
                  <Bot className="h-6 w-6 text-primary" />
                  <h3 className="mt-4 font-display text-2xl font-black">
                    {isKid ? "Koçun seni dinliyor" : "Koç akışı hazır"}
                  </h3>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    {isKid
                      ? "Harçlığın, kumbaran veya merak ettiğin bir şey hakkında soru sorabilirsin. Örneğin: 'Faiz nedir?' ya da 'Harçlığımı nasıl biriktiririm?'"
                      : "Son sohbetin varsa burada açılır; yeni konuşma başlatmak için üstteki düğmeyi kullanabilirsin."}
                  </p>
                  <button
                    type="button"
                    onClick={() => setDraft(activeSuggestion)}
                    className="mt-4 w-full rounded-2xl border border-border/70 bg-background/75 px-4 py-3 text-left transition-colors hover:border-primary/45 hover:bg-card"
                  >
                    <span className="flex items-center gap-2 text-[0.7rem] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                      <Sparkles className="h-3.5 w-3.5 text-primary" />
                      Deneyebileceğin soru
                    </span>
                    <span
                      key={activeSuggestion}
                      className="suggestion-rotate mt-2 block text-sm font-bold text-foreground"
                    >
                      {activeSuggestion}
                    </span>
                  </button>
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
          </div>
        ) : (
          <div id="tools-panel" role="tabpanel" className="h-full overflow-y-auto p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="eyebrow">Kanıt defteri</p>
                <h3 className="mt-1 font-display text-2xl font-black tracking-[-0.04em]">
                  Araç izi
                </h3>
              </div>
              {isStreaming ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : null}
            </div>
            {toolTrace.length === 0 ? (
              <p className="mt-4 text-sm leading-6 text-muted-foreground">
                İlk araç çağrısı burada görünecek. Sohbet sekmesi kalabalıklaşmadan yanıtın hangi
                veriye dayandığını izleyebilirsin.
              </p>
            ) : (
              <div className="mt-4 space-y-2">
                {toolTrace.map((item) => (
                  <div
                    key={item.id}
                    className="flex flex-col gap-1 rounded-2xl border border-border/60 bg-card/70 px-3 py-2 text-xs sm:flex-row sm:items-center sm:justify-between sm:gap-3"
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
      </div>

      <form
        className="bg-muted/62 shrink-0 space-y-2 rounded-[1.75rem] border border-border/70 p-2"
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
              disabled={isStreaming || isHydrating}
              onChange={handleFileChange}
            />
            <ImagePlus className="h-4 w-4" />
            <span className="sr-only">Fiş ekle</span>
          </label>
          <Input
            placeholder={activeSuggestion}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            disabled={isStreaming || isHydrating}
          />
          <Button
            type="submit"
            className="min-h-11"
            aria-label="Mesaj gönder"
            disabled={isStreaming || isHydrating || !draft.trim()}
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
