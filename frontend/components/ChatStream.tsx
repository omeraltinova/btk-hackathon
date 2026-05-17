"use client";

import {
  Bot,
  Check,
  ImagePlus,
  Loader2,
  MessageSquareText,
  Mic,
  Plus,
  Send,
  Sparkles,
  Volume2,
  VolumeX,
  Wrench,
  X,
  XCircle,
} from "lucide-react";
import { type ChangeEvent, type FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

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
import {
  clearPendingChatMessage,
  readActiveConversationId,
  readPendingChatMessage,
  rememberActiveConversationId,
  type PendingChatMessage,
} from "@/lib/chat-session";
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
  approval?: ApprovalRequestItem;
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

type ApprovalRequestItem = {
  approvalId: string;
  toolName: string;
  actionLabel: string;
  summary: string;
  details: string[];
  input: ChatToolPayload;
  status: "pending" | "approved" | "rejected";
};

type SpeechRecognitionAlternative = {
  transcript: string;
};

type SpeechRecognitionResult = {
  0?: SpeechRecognitionAlternative;
};

type SpeechRecognitionEventLike = {
  results: ArrayLike<SpeechRecognitionResult>;
};

type SpeechRecognitionErrorLike = {
  error?: string;
};

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorLike) => void) | null;
  onend: (() => void) | null;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

const ADULT_SUGGESTIONS = [
  "Bu ay markete ne kadar harcadım?",
  "Market harcamam ay ay nasıl değişti?",
  "Hedeflerimi göster",
  "Aboneliklerim nasıl gidiyor?",
  "Çocuğuma faiz nedir kumbarayla anlat",
] as const;

const KID_SUGGESTIONS = [
  "Harçlığımı nasıl biriktiririm?",
  "Faiz nedir, kumbarayla anlatır mısın?",
  "Bu ay nereye para harcamışım?",
  "Bayram paramı nasıl saklamalıyım?",
] as const;

function describeToolInput(input: ChatToolPayload): string {
  if ("chart_type" in input) {
    let chartType = "Çubuk grafik";
    if (input.chart_type === "pie") chartType = "Pasta grafik";
    if (input.chart_type === "monthly") chartType = "Aylık trend";
    const days = typeof input.days === "number" ? input.days : 30;
    return `${chartType} / son ${days} gün`;
  }
  if ("category" in input || "days" in input) {
    const category = typeof input.category === "string" ? input.category : "Tüm kategoriler";
    const days = typeof input.days === "number" ? input.days : 30;
    return `${category} / son ${days} gün`;
  }
  if ("only_active" in input) return "Aktif kayıtlar";
  if ("status" in input) return input.status === "all" ? "Tüm hedefler" : "Aktif hedefler";
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
    const netTotal =
      typeof result.monthly_net_total_formatted === "string"
        ? result.monthly_net_total_formatted
        : typeof result.monthly_total_formatted === "string"
          ? result.monthly_total_formatted
          : "0,00 ₺";
    const incomeTotal =
      typeof result.monthly_income_total_formatted === "string"
        ? result.monthly_income_total_formatted
        : "0,00 ₺";
    const expenseTotal =
      typeof result.monthly_expense_total_formatted === "string"
        ? result.monthly_expense_total_formatted
        : "0,00 ₺";
    const count = typeof result.count === "number" ? result.count : 0;
    return `${netTotal} net / gelir ${incomeTotal} / gider ${expenseTotal} / ${count} kayıt`;
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
  if (event.tool_name === "get_saving_goals" || event.tool_name === "visualize_saving_goals") {
    const count = typeof result.count === "number" ? result.count : 0;
    return event.tool_name === "visualize_saving_goals"
      ? `Hedef grafiği hazır / ${count} hedef`
      : `${count} hedef`;
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

function approvalFromEvent(
  event: Extract<ChatStreamEvent, { type: "approval_required" }>,
): ApprovalRequestItem {
  return {
    approvalId: event.approval_id,
    toolName: event.tool_name,
    actionLabel: event.action_label,
    summary: event.summary,
    details: event.details,
    input: event.input,
    status: "pending",
  };
}

function approvalStatusText(status: ApprovalRequestItem["status"]): string {
  if (status === "approved") return "Onaylandı";
  if (status === "rejected") return "Reddedildi";
  return "Onay bekliyor";
}

function renderApprovalInput(input: ChatToolPayload): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(input)) {
    if (value === null || value === undefined || key === "message") continue;
    parts.push(`${key}: ${String(value)}`);
  }
  return parts.join(" · ");
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

function ApprovalCard({
  approval,
  disabled,
  onDecision,
}: {
  approval: ApprovalRequestItem;
  disabled: boolean;
  onDecision: (approval: ApprovalRequestItem, decision: "approved" | "rejected") => void;
}) {
  const inputText = renderApprovalInput(approval.input);

  return (
    <section className="cash-envelope overflow-hidden px-4 py-4 text-sm shadow-sm sm:px-5">
      <div className="relative z-10 space-y-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="eyebrow">Onay fişi</p>
            <h4 className="mt-1 font-display text-xl font-black tracking-tight">
              {approval.actionLabel}
            </h4>
          </div>
          <span
            className={cn(
              "rounded-full border px-2.5 py-1 text-[0.7rem] font-black uppercase tracking-[0.12em]",
              approval.status === "pending"
                ? "border-accent/55 bg-accent/25 text-accent-foreground"
                : "bg-primary/12 border-primary/35 text-foreground",
            )}
          >
            {approvalStatusText(approval.status)}
          </span>
        </div>
        <p className="font-semibold leading-6 text-foreground">{approval.summary}</p>
        {approval.details.length > 0 ? (
          <ul className="space-y-1 text-muted-foreground">
            {approval.details.map((detail) => (
              <li key={detail} className="flex gap-2">
                <span aria-hidden="true">-</span>
                <span>{detail}</span>
              </li>
            ))}
          </ul>
        ) : null}
        {inputText ? (
          <p className="rounded-2xl border border-border/65 bg-background/55 px-3 py-2 text-xs font-semibold text-muted-foreground">
            {inputText}
          </p>
        ) : null}
        {approval.status === "pending" ? (
          <div className="flex flex-col gap-2 sm:flex-row">
            <Button
              type="button"
              size="sm"
              onClick={() => onDecision(approval, "approved")}
              disabled={disabled}
              className="min-h-10"
            >
              {disabled ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Check className="h-4 w-4" />
              )}
              Onayla
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => onDecision(approval, "rejected")}
              disabled={disabled}
              className="min-h-10"
            >
              <XCircle className="h-4 w-4" />
              Reddet
            </Button>
          </div>
        ) : null}
      </div>
    </section>
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

function textForSpeech(value: string): string {
  return value
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/[*_`#>~-]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function speakAssistantAnswer(text: string) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  const content = textForSpeech(text);
  if (!content) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(content);
  utterance.lang = "tr-TR";
  window.speechSynthesis.speak(utterance);
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
  const [supportsSpeechInput, setSupportsSpeechInput] = useState(false);
  const [showVoiceHint, setShowVoiceHint] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [voiceReplies, setVoiceReplies] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const pendingMessageRef = useRef<PendingChatMessage | null>(null);
  const pendingMessageStartedRef = useRef(false);
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
        const pendingMessage = pendingMessageRef.current ?? readPendingChatMessage();
        pendingMessageRef.current = pendingMessage;
        let targetId = pendingMessage?.startNew ? null : readActiveConversationId();
        if (!targetId) {
          if (pendingMessage?.startNew) {
            rememberActiveConversationId(null);
          } else {
            const conversations = await api<ConversationListItem[]>("/api/conversations?limit=1", {
              silent: true,
            });
            targetId = conversations[0]?.id ?? null;
          }
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
    const isSupported =
      typeof window !== "undefined" &&
      ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
    setSupportsSpeechInput(isSupported);
    if (isSupported && typeof window !== "undefined") {
      try {
        const seen = window.localStorage.getItem("cuzdan-kocu.voice-hint-shown");
        if (!seen) {
          setShowVoiceHint(true);
          const timer = window.setTimeout(() => {
            setShowVoiceHint(false);
            try {
              window.localStorage.setItem("cuzdan-kocu.voice-hint-shown", "1");
            } catch {
              // localStorage failure is non-blocking.
            }
          }, 8000);
          return () => {
            window.clearTimeout(timer);
            recognitionRef.current?.abort();
            if (typeof window !== "undefined" && "speechSynthesis" in window) {
              window.speechSynthesis.cancel();
            }
          };
        }
      } catch {
        // Ignore localStorage read failures; hint just stays off.
      }
    }
    return () => {
      recognitionRef.current?.abort();
      if (typeof window !== "undefined" && "speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  useEffect(() => {
    setVoiceReplies(isKid);
  }, [isKid]);

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

  const applyStreamEvent = useCallback((event: ChatStreamEvent, assistantId: string) => {
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
    if (event.type === "approval_required") {
      const approval = approvalFromEvent(event);
      setMessages((current) =>
        current.map((message) => (message.id === assistantId ? { ...message, approval } : message)),
      );
      setToolTrace((current) => [
        {
          id: crypto.randomUUID(),
          name: event.tool_name,
          status: "running",
          detail: "Kullanıcı onayı bekleniyor",
        },
        ...current,
      ]);
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
  }, []);

  const sendMessage = useCallback(
    async (
      text: string,
      options: {
        receipt?: ReceiptAttachment | null;
        resetConversation?: boolean;
        approvalId?: string;
        approvalDecision?: "approved" | "rejected";
      } = {},
    ): Promise<boolean> => {
      const trimmedText = text.trim();
      if (!trimmedText || isStreaming || isHydrating) return false;

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      const assistantId = crypto.randomUUID();
      const receipt = options.receipt ?? null;
      const targetConversationId = options.resetConversation ? null : conversationId;
      let assistantText = "";

      if (options.resetConversation) {
        rememberActiveConversationId(null);
        setConversationId(null);
        setToolTrace([]);
      }

      setMessages((current) => {
        const nextMessages = [
          { id: crypto.randomUUID(), role: "user" as const, content: trimmedText },
          { id: assistantId, role: "assistant" as const, content: "", isStreaming: true },
        ];
        return options.resetConversation ? nextMessages : [...current, ...nextMessages];
      });
      setDraft("");
      setAttachment(null);
      setFileError(null);
      setHistoryError(null);
      setActivePanel("chat");
      setIsStreaming(true);

      try {
        await streamChat(
          {
            message: trimmedText,
            conversation_id: targetConversationId,
            receipt_image_base64: receipt?.base64 ?? null,
            receipt_filename: receipt?.filename ?? null,
            receipt_content_type: receipt?.contentType ?? null,
            approval_id: options.approvalId ?? null,
            approval_decision: options.approvalDecision ?? null,
          },
          (streamEvent) => {
            if (streamEvent.type === "delta") assistantText += streamEvent.content;
            applyStreamEvent(streamEvent, assistantId);
          },
          { signal: controller.signal },
        );
        if (voiceReplies) speakAssistantAnswer(assistantText);
        return true;
      } catch (err) {
        if ((err as Error).name === "AbortError") return false;
        const message =
          err instanceof Error ? err.message : "Koç akışı kesildi, tekrar dener misin?";
        setMessages((current) =>
          current.map((item) =>
            item.id === assistantId ? { ...item, content: message, isStreaming: false } : item,
          ),
        );
        return false;
      } finally {
        setIsStreaming(false);
      }
    },
    [applyStreamEvent, conversationId, isHydrating, isStreaming, voiceReplies],
  );

  useEffect(() => {
    if (isHydrating || isStreaming || pendingMessageStartedRef.current) return;
    const pendingMessage = pendingMessageRef.current ?? readPendingChatMessage();
    if (!pendingMessage) return;
    pendingMessageRef.current = pendingMessage;
    pendingMessageStartedRef.current = true;
    clearPendingChatMessage();
    void sendMessage(pendingMessage.message, { resetConversation: pendingMessage.startNew });
  }, [isHydrating, isStreaming, sendMessage]);

  const sendApprovalDecision = useCallback(
    (approval: ApprovalRequestItem, decision: "approved" | "rejected") => {
      if (isStreaming || isHydrating) return;
      setMessages((current) =>
        current.map((message) =>
          message.approval?.approvalId === approval.approvalId
            ? {
                ...message,
                approval: {
                  ...message.approval,
                  status: decision === "approved" ? "approved" : "rejected",
                },
              }
            : message,
        ),
      );
      const text = decision === "approved" ? "Bu işlemi onaylıyorum." : "Bu işlemi reddediyorum.";
      void sendMessage(text, {
        approvalId: approval.approvalId,
        approvalDecision: decision,
      });
    },
    [isHydrating, isStreaming, sendMessage],
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || isStreaming || isHydrating) return;
    void sendMessage(text, { receipt: attachment });
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

  function dismissVoiceHint() {
    if (!showVoiceHint) return;
    setShowVoiceHint(false);
    try {
      window.localStorage.setItem("cuzdan-kocu.voice-hint-shown", "1");
    } catch {
      // best-effort persistence.
    }
  }

  function handleVoiceInput() {
    if (isStreaming || isHydrating) return;
    const SpeechRecognitionConstructorRef =
      window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!SpeechRecognitionConstructorRef) {
      toast.error("Bu tarayıcı sesli giriş desteklemiyor.");
      return;
    }
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
      return;
    }
    recognitionRef.current?.abort();
    const recognition = new SpeechRecognitionConstructorRef();
    recognitionRef.current = recognition;
    recognition.lang = "tr-TR";
    recognition.interimResults = false;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      const transcript = event.results[0]?.[0]?.transcript?.trim();
      if (!transcript) return;
      setDraft((current) => (current.trim() ? `${current.trim()} ${transcript}` : transcript));
    };
    recognition.onerror = (event) => {
      if (event.error === "aborted") return;
      toast.error("Ses alınamadı, tekrar dener misin?");
      setIsListening(false);
    };
    recognition.onend = () => {
      setIsListening(false);
      if (recognitionRef.current === recognition) recognitionRef.current = null;
    };
    try {
      setIsListening(true);
      recognition.start();
    } catch {
      setIsListening(false);
      toast.error("Mikrofon başlatılamadı.");
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
    if (typeof window !== "undefined" && "speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
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
            className="h-full overflow-y-auto px-3 py-3 sm:px-4 sm:py-4 lg:px-6 xl:px-8"
          >
            <div className="space-y-4 lg:space-y-6">
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
                  <div className="mt-4">
                    <span className="flex items-center gap-2 text-[0.7rem] font-bold uppercase tracking-[0.18em] text-muted-foreground">
                      <Sparkles className="h-3.5 w-3.5 text-primary" />
                      Deneyebileceğin sorular
                    </span>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {suggestions.map((suggestion) => (
                        <button
                          key={suggestion}
                          type="button"
                          onClick={() => setDraft(suggestion)}
                          className="rounded-2xl border border-border/70 bg-background/75 px-3 py-2 text-left text-sm font-medium text-foreground transition-colors hover:border-primary/45 hover:bg-card"
                        >
                          {suggestion}
                        </button>
                      ))}
                    </div>
                  </div>
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
                    {message.approval ? (
                      <ApprovalCard
                        approval={message.approval}
                        disabled={isStreaming || isHydrating}
                        onDecision={sendApprovalDecision}
                      />
                    ) : null}
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
        <div className="flex flex-wrap items-center justify-between gap-2 px-2 text-xs font-semibold text-muted-foreground">
          <button
            type="button"
            onClick={() => setVoiceReplies((current) => !current)}
            className="inline-flex items-center gap-1.5 rounded-full px-2 py-1 transition-colors hover:bg-background/70 hover:text-foreground"
          >
            {voiceReplies ? (
              <Volume2 className="h-3.5 w-3.5" />
            ) : (
              <VolumeX className="h-3.5 w-3.5" />
            )}
            {voiceReplies ? "Sesli oku açık" : "Sesli oku kapalı"}
          </button>
          {supportsSpeechInput ? (
            <span>{isListening ? "Dinliyorum..." : "Mikrofon hazır"}</span>
          ) : null}
        </div>
        <div
          className={cn(
            "grid gap-2",
            supportsSpeechInput
              ? "grid-cols-[2.75rem_2.75rem_minmax(0,1fr)_2.75rem]"
              : "grid-cols-[2.75rem_minmax(0,1fr)_2.75rem]",
          )}
        >
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
          {supportsSpeechInput ? (
            <div className="relative inline-flex items-center justify-center">
              <button
                type="button"
                aria-label={isListening ? "Ses kaydını durdur" : "Sesli yaz"}
                disabled={isStreaming || isHydrating}
                onClick={() => {
                  dismissVoiceHint();
                  handleVoiceInput();
                }}
                className={cn(
                  "inline-flex h-11 w-11 items-center justify-center rounded-full border border-border bg-background/70 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-50",
                  isListening ? "border-primary bg-primary/10 text-primary" : "",
                )}
              >
                <Mic className="h-4 w-4" />
              </button>
              {showVoiceHint ? (
                <div
                  role="status"
                  className="absolute bottom-full left-1/2 z-10 mb-2 w-max max-w-[14rem] -translate-x-1/2 rounded-2xl border border-primary/35 bg-card px-3 py-2 text-xs font-semibold text-foreground shadow-lg"
                >
                  <span className="block leading-snug">Mikrofona dokun, koça sesli soru sor.</span>
                  <button
                    type="button"
                    onClick={dismissVoiceHint}
                    aria-label="İpucunu kapat"
                    className="absolute -right-1.5 -top-1.5 grid h-5 w-5 place-items-center rounded-full border border-border bg-background text-muted-foreground hover:text-foreground"
                  >
                    <X className="h-3 w-3" />
                  </button>
                  <span
                    aria-hidden="true"
                    className="absolute left-1/2 top-full -mt-px h-2 w-2 -translate-x-1/2 rotate-45 border-b border-r border-primary/35 bg-card"
                  />
                </div>
              ) : null}
            </div>
          ) : null}
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
