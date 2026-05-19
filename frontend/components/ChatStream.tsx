"use client";

import {
  Bot,
  Check,
  Download,
  FileText,
  Headphones,
  ImagePlus,
  Loader2,
  MessageSquareText,
  Mic,
  MicOff,
  Plus,
  Send,
  Sparkles,
  Square,
  Volume2,
  VolumeX,
  Wrench,
  X,
  XCircle,
} from "lucide-react";
import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { ChatChart } from "@/components/ChatChart";
import { ChatMessage } from "@/components/ChatMessage";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ACTIVE_PROFILE_EVENT } from "@/lib/active-profile";
import { api, apiDownload, ApiError } from "@/lib/api";
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
import { GeminiLiveVoiceSession } from "@/lib/live-voice";
import { playTts, stopActiveSpeech } from "@/lib/tts";
import type {
  ChatStreamEvent,
  ChatToolPayload,
  ConversationListItem,
  ConversationMessages,
  VoiceSessionResponse,
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
type VoiceInputMode = "provider" | "browser";
type VoiceChatMode = "off" | "cascade" | "gemini-live";
type VoiceChatStatus =
  | "idle"
  | "connecting"
  | "listening"
  | "recording"
  | "thinking"
  | "synthesizing"
  | "speaking";
type VoiceTranscriptSource = "manual" | "voice-chat";
type VoicePauseReason = "user" | "approval" | null;

type SendMessageOptions = {
  receipt?: ReceiptAttachment | null;
  resetConversation?: boolean;
  approvalId?: string;
  approvalDecision?: "approved" | "rejected";
  speakResponse?: boolean;
  onDelta?: (content: string, fullText: string) => void;
};

type SendMessageResult = {
  ok: boolean;
  assistantText: string;
};

const CASCADE_MIN_RMS_THRESHOLD = 0.018;
const CASCADE_NOISE_MULTIPLIER = 3.2;
const CASCADE_NOISE_ALPHA = 0.04;
const CASCADE_MIN_SPEECH_FRAMES = 4;
const CASCADE_SILENCE_MS = 950;
const CASCADE_MIN_RECORDING_MS = 550;
const CASCADE_RESTART_DELAY_MS = 420;
const CASCADE_RECOVERY_DELAY_MS = 900;

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
  if (event.tool_name === "generate_monthly_report") {
    return typeof result.download_url === "string" ? "Rapor hazır" : "Rapor oluşturulamadı";
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
  if (attachment.type === "report") {
    return <ReportAttachment key={attachment.id} attachment={attachment} />;
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

function reportFromToolResult(result: ChatToolPayload): ChatAttachmentItem | null {
  if (
    typeof result.report_id !== "string" ||
    typeof result.download_url !== "string" ||
    typeof result.filename !== "string"
  ) {
    return null;
  }
  return {
    id: crypto.randomUUID(),
    type: "report",
    reportId: result.report_id,
    downloadUrl: result.download_url,
    filename: result.filename,
    title: typeof result.title === "string" ? result.title : "Aylık Koç Raporu",
    format: typeof result.format === "string" ? result.format : "docx",
  };
}

function ReportAttachment({
  attachment,
}: {
  attachment: Extract<ChatAttachmentItem, { type: "report" }>;
}) {
  const [isDownloading, setIsDownloading] = useState(false);

  async function handleDownload() {
    if (isDownloading) return;
    setIsDownloading(true);
    try {
      await apiDownload(attachment.downloadUrl, attachment.filename);
    } catch (err) {
      toast.error(friendlyError(err, "Rapor indirilemedi."));
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <section className="cash-envelope overflow-hidden px-4 py-4 shadow-sm sm:px-5">
      <div className="relative z-10 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="bg-primary/12 grid h-11 w-11 shrink-0 place-items-center rounded-2xl text-primary">
            <FileText className="h-5 w-5" />
          </span>
          <div>
            <p className="eyebrow">DOCX rapor</p>
            <h4 className="mt-1 font-display text-xl font-black tracking-tight">
              {attachment.title}
            </h4>
            <p className="mt-1 text-sm font-semibold text-muted-foreground">
              {attachment.filename}
            </p>
          </div>
        </div>
        <Button
          type="button"
          onClick={handleDownload}
          disabled={isDownloading}
          className="min-h-10"
        >
          {isDownloading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          İndir
        </Button>
      </div>
    </section>
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

function preferredRecordingMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  const candidates = ["audio/ogg;codecs=opus", "audio/ogg", "audio/webm;codecs=opus", "audio/webm"];
  return candidates.find((candidate) => MediaRecorder.isTypeSupported(candidate));
}

function filenameForAudioType(contentType: string): string {
  const normalized = contentType.split(";", 1)[0]?.trim().toLowerCase();
  if (normalized === "audio/ogg") return "ses-kaydi.ogg";
  if (normalized === "audio/webm") return "ses-kaydi.webm";
  if (normalized === "audio/wav" || normalized === "audio/x-wav") return "ses-kaydi.wav";
  if (normalized === "audio/mpeg" || normalized === "audio/mp3") return "ses-kaydi.mp3";
  return "ses-kaydi.bin";
}

function stopMediaStream(stream: MediaStream | null) {
  stream?.getTracks().forEach((track) => track.stop());
}

function voiceStatusTitle(mode: VoiceChatMode, status: VoiceChatStatus): string {
  if (mode === "gemini-live") {
    return status === "connecting" ? "Canlı hat kuruluyor" : "Canlı ses hattı açık";
  }
  if (status === "recording") return "Seni dinliyorum";
  if (status === "thinking") return "Koç cevabı hazırlıyor";
  if (status === "synthesizing") return "Yanıt sese çevriliyor";
  if (status === "speaking") return "Yanıt sesli okunuyor";
  if (status === "connecting") return "Mikrofon hazırlanıyor";
  return "Konuşmaya başlayabilirsin";
}

function voiceStatusDescription(
  mode: VoiceChatMode,
  status: VoiceChatStatus,
  pauseReason: VoicePauseReason,
): string {
  if (mode === "gemini-live") {
    return "Gemini Live sadece ses hattı; finans cevabı yine güvenli koç akışından geliyor.";
  }
  if (pauseReason === "user") {
    return "Mikrofon kapalı. Hazır olduğunda tekrar açıp konuşmaya devam edebilirsin.";
  }
  if (status === "recording") {
    return "Cümleni bitirdiğinde otomatik göndereceğim; tekrar tuşa basmana gerek yok.";
  }
  if (status === "thinking") {
    return "Ses metne çevrildi, mevcut sohbet koçu yanıtı hazırlıyor.";
  }
  if (status === "synthesizing") {
    return "Koçun cevabı hazır; şimdi sesli yanıt hazırlanıyor.";
  }
  if (status === "speaking") {
    return "Yanıt bitince mikrofon yeniden dinlemeye dönecek.";
  }
  return "Bu panel açıkken konuşmayı algılar, bırakınca gönderir ve yanıtı sesli okur.";
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
  const [supportsProviderRecording, setSupportsProviderRecording] = useState(false);
  const [supportsBrowserSpeechInput, setSupportsBrowserSpeechInput] = useState(false);
  const [showVoiceHint, setShowVoiceHint] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceChatMode, setVoiceChatMode] = useState<VoiceChatMode>("off");
  const [voiceChatStatus, setVoiceChatStatus] = useState<VoiceChatStatus>("idle");
  const [voicePauseReason, setVoicePauseReason] = useState<VoicePauseReason>(null);
  const [voiceReplies, setVoiceReplies] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const fallbackTranscriptRef = useRef("");
  const activeVoiceModeRef = useRef<VoiceInputMode | null>(null);
  const liveVoiceRef = useRef<GeminiLiveVoiceSession | null>(null);
  const sendMessageRef = useRef<
    ((text: string, options?: SendMessageOptions) => Promise<SendMessageResult>) | null
  >(null);
  const voiceChatModeRef = useRef<VoiceChatMode>("off");
  const voiceChatStatusRef = useRef<VoiceChatStatus>("idle");
  const voicePauseReasonRef = useRef<VoicePauseReason>(null);
  const voiceApprovalPendingRef = useRef(false);
  const isStreamingRef = useRef(false);
  const isHydratingRef = useRef(true);
  const isTranscribingRef = useRef(false);
  const cascadeVoiceActiveRef = useRef(false);
  const cascadeAudioContextRef = useRef<AudioContext | null>(null);
  const cascadeAnalyserRef = useRef<AnalyserNode | null>(null);
  const cascadeAudioSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const cascadeAudioDataRef = useRef<Uint8Array<ArrayBuffer> | null>(null);
  const cascadeRafRef = useRef<number | null>(null);
  const cascadeSpeechStartedRef = useRef(false);
  const cascadeSilenceStartedRef = useRef<number | null>(null);
  const cascadeSpeechFrameCountRef = useRef(0);
  const cascadeNoiseFloorRef = useRef(0);
  const cascadeRecorderStartedAtRef = useRef(0);
  const voiceSessionRef = useRef(0);
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
    const browserSpeechSupported =
      typeof window !== "undefined" &&
      ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
    const providerRecordingSupported =
      typeof window !== "undefined" &&
      typeof navigator !== "undefined" &&
      Boolean(navigator.mediaDevices?.getUserMedia) &&
      typeof MediaRecorder !== "undefined";
    setSupportsBrowserSpeechInput(browserSpeechSupported);
    setSupportsProviderRecording(providerRecordingSupported);
    setSupportsSpeechInput(browserSpeechSupported || providerRecordingSupported);
    if ((browserSpeechSupported || providerRecordingSupported) && typeof window !== "undefined") {
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
            mediaRecorderRef.current?.stop();
            stopMediaStream(mediaStreamRef.current);
            stopActiveSpeech();
          };
        }
      } catch {
        // Ignore localStorage read failures; hint just stays off.
      }
    }
    return () => {
      recognitionRef.current?.abort();
      mediaRecorderRef.current?.stop();
      stopMediaStream(mediaStreamRef.current);
      stopActiveSpeech();
    };
  }, []);

  useEffect(() => {
    setVoiceReplies(isKid);
  }, [isKid]);

  useEffect(() => {
    voiceChatModeRef.current = voiceChatMode;
  }, [voiceChatMode]);

  useEffect(() => {
    voiceChatStatusRef.current = voiceChatStatus;
  }, [voiceChatStatus]);

  useEffect(() => {
    voicePauseReasonRef.current = voicePauseReason;
  }, [voicePauseReason]);

  useEffect(() => {
    isStreamingRef.current = isStreaming;
  }, [isStreaming]);

  useEffect(() => {
    isHydratingRef.current = isHydrating;
  }, [isHydrating]);

  useEffect(() => {
    isTranscribingRef.current = isTranscribing;
  }, [isTranscribing]);

  useEffect(() => {
    return () => {
      cascadeVoiceActiveRef.current = false;
      if (cascadeRafRef.current !== null) {
        window.cancelAnimationFrame(cascadeRafRef.current);
        cascadeRafRef.current = null;
      }
      cascadeAudioSourceRef.current?.disconnect();
      cascadeAnalyserRef.current?.disconnect();
      cascadeAudioSourceRef.current = null;
      cascadeAnalyserRef.current = null;
      cascadeAudioDataRef.current = null;
      const context = cascadeAudioContextRef.current;
      cascadeAudioContextRef.current = null;
      if (context && context.state !== "closed") void context.close();
      void liveVoiceRef.current?.stop();
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
      const report = reportFromToolResult(event.result);
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
      if (report) {
        setMessages((current) =>
          current.map((message) =>
            message.id === assistantId
              ? { ...message, attachments: [...(message.attachments ?? []), report] }
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
      const imageAttachment: ChatAttachmentItem = {
        id: crypto.randomUUID(),
        type: "image",
        imageUrl: event.image_url,
        altText: event.alt_text,
      };
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                attachments: [...(message.attachments ?? []), imageAttachment],
              }
            : message,
        ),
      );
      return;
    }
    if (event.type === "approval_required") {
      if (voiceChatModeRef.current !== "off") {
        voiceApprovalPendingRef.current = true;
        pauseCascadeListening();
        setVoiceChatStatus("idle");
      }
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
  }

  async function sendMessage(
    text: string,
    options: SendMessageOptions = {},
  ): Promise<SendMessageResult> {
    const trimmedText = text.trim();
    if (!trimmedText || isStreaming || isHydrating) {
      return { ok: false, assistantText: "" };
    }

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
    isStreamingRef.current = true;
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
          if (streamEvent.type === "delta") {
            assistantText += streamEvent.content;
            options.onDelta?.(streamEvent.content, assistantText);
          }
          applyStreamEvent(streamEvent, assistantId);
        },
        { signal: controller.signal },
      );
      if (options.speakResponse ?? voiceReplies) {
        void playTts(assistantText).catch((err) => {
          toast.error(err instanceof ApiError ? err.detail : "Sesli okuma başlatılamadı.");
        });
      }
      return { ok: true, assistantText };
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        return { ok: false, assistantText: "" };
      }
      const message = err instanceof Error ? err.message : "Koç akışı kesildi, tekrar dener misin?";
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantId ? { ...item, content: message, isStreaming: false } : item,
        ),
      );
      return { ok: false, assistantText: "" };
    } finally {
      isStreamingRef.current = false;
      setIsStreaming(false);
    }
  }

  sendMessageRef.current = sendMessage;

  useEffect(() => {
    if (isHydrating || isStreaming || pendingMessageStartedRef.current) return;
    const pendingMessage = pendingMessageRef.current ?? readPendingChatMessage();
    if (!pendingMessage) return;
    pendingMessageRef.current = pendingMessage;
    pendingMessageStartedRef.current = true;
    clearPendingChatMessage();
    void sendMessageRef.current?.(pendingMessage.message, {
      resetConversation: pendingMessage.startNew,
    });
  }, [isHydrating, isStreaming]);

  function markApprovalDecision(approval: ApprovalRequestItem, decision: "approved" | "rejected") {
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
  }

  function pauseCascadeListening(reason: Exclude<VoicePauseReason, null> = "approval") {
    voicePauseReasonRef.current = reason;
    setVoicePauseReason(reason);
    cancelCascadeMonitor();
    recognitionRef.current?.abort();
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      voiceSessionRef.current += 1;
      try {
        recorder.stop();
      } catch {
        // The recorder may already be stopping; stale events are invalidated above.
      }
    }
    mediaRecorderRef.current = null;
    recordedChunksRef.current = [];
    fallbackTranscriptRef.current = "";
    activeVoiceModeRef.current = null;
    isTranscribingRef.current = false;
    setIsListening(false);
    setIsTranscribing(false);
  }

  function resumeCascadeListening() {
    if (!cascadeVoiceActiveRef.current || voiceChatModeRef.current !== "cascade") return;
    if (voicePauseReasonRef.current === "user") return;
    if (voiceApprovalPendingRef.current || isStreamingRef.current || isTranscribingRef.current)
      return;
    voicePauseReasonRef.current = null;
    setVoicePauseReason(null);
    setVoiceChatStatus("listening");
    if (cascadeAnalyserRef.current) {
      monitorCascadeAudio();
    } else {
      startBrowserVoiceInput();
    }
  }

  function recoverCascadeListening(delayMs = CASCADE_RECOVERY_DELAY_MS) {
    if (!cascadeVoiceActiveRef.current || voiceChatModeRef.current !== "cascade") return;
    window.setTimeout(() => {
      resumeCascadeListening();
    }, delayMs);
  }

  function sendApprovalDecision(approval: ApprovalRequestItem, decision: "approved" | "rejected") {
    if (isStreaming || isHydrating) return;
    markApprovalDecision(approval, decision);
    const text = decision === "approved" ? "Bu işlemi onaylıyorum." : "Bu işlemi reddediyorum.";
    void sendMessage(text, {
      approvalId: approval.approvalId,
      approvalDecision: decision,
    });
  }

  function handleApprovalDecision(
    approval: ApprovalRequestItem,
    decision: "approved" | "rejected",
  ) {
    if (voiceChatModeRef.current === "cascade") {
      void sendVoiceApprovalDecision(approval, decision);
      return;
    }
    sendApprovalDecision(approval, decision);
  }

  function setCascadeUserPaused(paused: boolean) {
    if (voiceChatModeRef.current !== "cascade") return;
    if (paused) {
      voicePauseReasonRef.current = "user";
      setVoicePauseReason("user");
      if (voiceChatStatusRef.current === "recording") {
        cancelCascadeMonitor();
        recognitionRef.current?.stop();
        const recorder = mediaRecorderRef.current;
        if (recorder && recorder.state === "recording") {
          setIsListening(false);
          setIsTranscribing(true);
          isTranscribingRef.current = true;
          setVoiceChatStatus("thinking");
          recorder.stop();
        } else {
          activeVoiceModeRef.current = null;
          setIsListening(false);
          setVoiceChatStatus("idle");
        }
      } else if (voiceChatStatusRef.current === "listening") {
        cancelCascadeMonitor();
        if (activeVoiceModeRef.current === "browser") {
          recognitionRef.current?.stop();
        } else {
          recognitionRef.current?.abort();
          activeVoiceModeRef.current = null;
        }
        setIsListening(false);
        setVoiceChatStatus("idle");
      }
      mediaStreamRef.current?.getAudioTracks().forEach((track) => {
        track.enabled = false;
      });
      return;
    }
    voicePauseReasonRef.current = null;
    setVoicePauseReason(null);
    mediaStreamRef.current?.getAudioTracks().forEach((track) => {
      track.enabled = true;
    });
    resumeCascadeListening();
  }

  function stopVoiceResponse() {
    stopActiveSpeech();
    if (voiceChatModeRef.current === "cascade") {
      if (isStreamingRef.current) {
        abortRef.current?.abort();
        isStreamingRef.current = false;
        setIsStreaming(false);
      }
      if (!voiceApprovalPendingRef.current) {
        window.setTimeout(() => {
          resumeCascadeListening();
        }, CASCADE_RESTART_DELAY_MS);
      }
    }
  }

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

  async function sendVoiceTranscript(transcript: string, source: VoiceTranscriptSource = "manual") {
    const trimmed = transcript.trim();
    if (!trimmed) return;
    const isVoiceChatTurn = source === "voice-chat" && voiceChatModeRef.current === "cascade";
    if (isVoiceChatTurn) {
      setVoiceChatStatus("thinking");
    }
    const result = await sendMessage(trimmed, { speakResponse: false });
    if (isVoiceChatTurn && result.ok && result.assistantText.trim()) {
      setVoiceChatStatus("synthesizing");
      try {
        await playTts(result.assistantText, {
          onPlaybackStart: () => setVoiceChatStatus("speaking"),
        });
      } catch (err) {
        toast.error(err instanceof ApiError ? err.detail : "Sesli yanıt başlatılamadı.");
      }
    } else if (!isVoiceChatTurn && result.ok && voiceReplies) {
      void playTts(result.assistantText).catch((err) => {
        toast.error(err instanceof ApiError ? err.detail : "Sesli okuma başlatılamadı.");
      });
    }
    if (isVoiceChatTurn && voiceApprovalPendingRef.current) {
      setVoiceChatStatus("idle");
      return;
    }
    if (isVoiceChatTurn && cascadeVoiceActiveRef.current) {
      window.setTimeout(() => {
        resumeCascadeListening();
      }, CASCADE_RESTART_DELAY_MS);
    }
  }

  async function sendVoiceApprovalDecision(
    approval: ApprovalRequestItem,
    decision: "approved" | "rejected",
  ) {
    if (isStreamingRef.current || isHydratingRef.current) return;
    pauseCascadeListening();
    voiceApprovalPendingRef.current = false;
    markApprovalDecision(approval, decision);
    setVoiceChatStatus("thinking");
    const text = decision === "approved" ? "Bu işlemi onaylıyorum." : "Bu işlemi reddediyorum.";
    const result = await sendMessage(text, {
      approvalId: approval.approvalId,
      approvalDecision: decision,
      speakResponse: false,
    });
    if (result.ok && result.assistantText.trim()) {
      setVoiceChatStatus("synthesizing");
      try {
        await playTts(result.assistantText, {
          onPlaybackStart: () => setVoiceChatStatus("speaking"),
        });
      } catch (err) {
        toast.error(err instanceof ApiError ? err.detail : "Sesli yanıt başlatılamadı.");
      }
    }
    if (voiceApprovalPendingRef.current) {
      setVoiceChatStatus("idle");
      return;
    }
    window.setTimeout(() => {
      resumeCascadeListening();
    }, CASCADE_RESTART_DELAY_MS);
  }

  function cancelCascadeMonitor() {
    if (cascadeRafRef.current !== null) {
      window.cancelAnimationFrame(cascadeRafRef.current);
      cascadeRafRef.current = null;
    }
  }

  async function closeCascadeAudioContext() {
    cancelCascadeMonitor();
    cascadeAudioSourceRef.current?.disconnect();
    cascadeAnalyserRef.current?.disconnect();
    cascadeAudioSourceRef.current = null;
    cascadeAnalyserRef.current = null;
    cascadeAudioDataRef.current = null;
    const context = cascadeAudioContextRef.current;
    cascadeAudioContextRef.current = null;
    if (context && context.state !== "closed") {
      try {
        await context.close();
      } catch {
        // Best-effort cleanup; browser may already be closing the context.
      }
    }
  }

  async function stopCascadeVoiceChat() {
    cascadeVoiceActiveRef.current = false;
    voiceSessionRef.current += 1;
    cancelCascadeMonitor();
    recognitionRef.current?.abort();
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      try {
        recorder.stop();
      } catch {
        // Stopping is best-effort; stale onstop events are invalidated above.
      }
    }
    mediaRecorderRef.current = null;
    recordedChunksRef.current = [];
    fallbackTranscriptRef.current = "";
    activeVoiceModeRef.current = null;
    voicePauseReasonRef.current = null;
    voiceApprovalPendingRef.current = false;
    stopActiveSpeech();
    stopMediaStream(mediaStreamRef.current);
    mediaStreamRef.current = null;
    await closeCascadeAudioContext();
    setIsListening(false);
    setIsTranscribing(false);
    isTranscribingRef.current = false;
    setVoicePauseReason(null);
    setVoiceChatMode("off");
    setVoiceChatStatus("idle");
  }

  async function stopGeminiLiveVoice() {
    const session = liveVoiceRef.current;
    liveVoiceRef.current = null;
    voiceApprovalPendingRef.current = false;
    setVoiceChatMode("off");
    setVoiceChatStatus("idle");
    if (session) await session.stop();
  }

  function startCascadeRecorder() {
    const stream = mediaStreamRef.current;
    if (!stream || mediaRecorderRef.current) return;
    const mimeType = preferredRecordingMimeType();
    const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    const sessionId = voiceSessionRef.current + 1;
    voiceSessionRef.current = sessionId;
    activeVoiceModeRef.current = "provider";
    recordedChunksRef.current = [];
    fallbackTranscriptRef.current = "";
    cascadeRecorderStartedAtRef.current = performance.now();
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) recordedChunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const chunks = recordedChunksRef.current;
      const contentType = recorder.mimeType || chunks[0]?.type || "application/octet-stream";
      mediaRecorderRef.current = null;
      recordedChunksRef.current = [];
      setIsListening(false);
      if (!cascadeVoiceActiveRef.current || sessionId !== voiceSessionRef.current) return;
      if (chunks.length === 0) {
        resumeCascadeListening();
        return;
      }
      setIsTranscribing(true);
      isTranscribingRef.current = true;
      void handleRecordedAudio({ chunks, contentType, sessionId, source: "voice-chat" });
    };
    recorder.onerror = () => {
      mediaRecorderRef.current = null;
      recordedChunksRef.current = [];
      setIsListening(false);
      setIsTranscribing(false);
      isTranscribingRef.current = false;
      activeVoiceModeRef.current = null;
      if (cascadeVoiceActiveRef.current) {
        toast.error("Ses kaydı kesildi, yeniden dinlemeye geçiyorum.");
        resumeCascadeListening();
      }
    };
    mediaRecorderRef.current = recorder;
    recorder.start();
    if (voicePauseReasonRef.current === "user") {
      recorder.stop();
      return;
    }
    setIsListening(true);
    setVoiceChatStatus("recording");
  }

  function monitorCascadeAudio() {
    cancelCascadeMonitor();
    cascadeSpeechStartedRef.current = false;
    cascadeSilenceStartedRef.current = null;
    cascadeSpeechFrameCountRef.current = 0;
    const tick = (timestamp: number) => {
      if (!cascadeVoiceActiveRef.current || voiceChatModeRef.current !== "cascade") return;
      if (isStreamingRef.current || isTranscribingRef.current) {
        cascadeRafRef.current = window.requestAnimationFrame(tick);
        return;
      }
      const analyser = cascadeAnalyserRef.current;
      const data = cascadeAudioDataRef.current;
      if (!analyser || !data) return;
      analyser.getByteTimeDomainData(data);
      let sumSquares = 0;
      for (const value of data) {
        const normalized = (value - 128) / 128;
        sumSquares += normalized * normalized;
      }
      const rms = Math.sqrt(sumSquares / data.length);
      const noiseFloor = cascadeNoiseFloorRef.current;
      const speechThreshold = Math.max(
        CASCADE_MIN_RMS_THRESHOLD,
        noiseFloor * CASCADE_NOISE_MULTIPLIER,
      );
      const hasSpeech = rms >= speechThreshold;
      if (!cascadeSpeechStartedRef.current) {
        if (hasSpeech) {
          cascadeSpeechFrameCountRef.current += 1;
          if (cascadeSpeechFrameCountRef.current >= CASCADE_MIN_SPEECH_FRAMES) {
            cascadeSpeechStartedRef.current = true;
            cascadeSilenceStartedRef.current = null;
            startCascadeRecorder();
          }
        } else if (voiceChatStatusRef.current !== "listening") {
          cascadeSpeechFrameCountRef.current = 0;
          setVoiceChatStatus("listening");
        } else {
          cascadeSpeechFrameCountRef.current = 0;
        }
      } else if (hasSpeech) {
        cascadeSilenceStartedRef.current = null;
      } else {
        cascadeSilenceStartedRef.current ??= timestamp;
        const silenceMs = timestamp - cascadeSilenceStartedRef.current;
        const recordingMs = timestamp - cascadeRecorderStartedAtRef.current;
        if (silenceMs >= CASCADE_SILENCE_MS && recordingMs >= CASCADE_MIN_RECORDING_MS) {
          cancelCascadeMonitor();
          const recorder = mediaRecorderRef.current;
          if (recorder && recorder.state === "recording") {
            setIsListening(false);
            setIsTranscribing(true);
            isTranscribingRef.current = true;
            recorder.stop();
          }
          return;
        }
      }
      if (!hasSpeech) {
        cascadeNoiseFloorRef.current = noiseFloor
          ? noiseFloor * (1 - CASCADE_NOISE_ALPHA) + rms * CASCADE_NOISE_ALPHA
          : rms;
      }
      cascadeRafRef.current = window.requestAnimationFrame(tick);
    };
    cascadeRafRef.current = window.requestAnimationFrame(tick);
  }

  async function startCascadeProviderLoop() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Mikrofon kaydı başlatılamadı.");
    }
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    mediaStreamRef.current = stream;
    stream.getAudioTracks().forEach((track) => {
      track.enabled = voicePauseReasonRef.current !== "user";
    });
    const context = new AudioContext();
    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    source.connect(analyser);
    cascadeAudioContextRef.current = context;
    cascadeAudioSourceRef.current = source;
    cascadeAnalyserRef.current = analyser;
    cascadeAudioDataRef.current = new Uint8Array(new ArrayBuffer(analyser.fftSize));
    cascadeNoiseFloorRef.current = 0;
    await context.resume();
    setVoiceChatStatus("listening");
    monitorCascadeAudio();
  }

  async function startCascadeVoiceChat() {
    if (isStreamingRef.current || isHydratingRef.current || isTranscribingRef.current) return;
    await stopCascadeVoiceChat();
    cascadeVoiceActiveRef.current = true;
    setVoiceChatMode("cascade");
    setVoiceChatStatus("connecting");
    if (supportsProviderRecording) {
      try {
        await startCascadeProviderLoop();
        return;
      } catch {
        await closeCascadeAudioContext();
        stopMediaStream(mediaStreamRef.current);
        mediaStreamRef.current = null;
        mediaRecorderRef.current = null;
        recordedChunksRef.current = [];
      }
    }
    if (supportsBrowserSpeechInput) {
      setVoiceChatStatus("listening");
      startBrowserVoiceInput();
      return;
    }
    cascadeVoiceActiveRef.current = false;
    setVoiceChatMode("off");
    setVoiceChatStatus("idle");
    toast.error("Bu tarayıcı sesli sohbeti desteklemiyor.");
  }

  async function startGeminiLiveVoice(session: VoiceSessionResponse) {
    if (!session.ephemeral_token || !session.model) {
      throw new Error("Canlı sesli sohbet bilgisi eksik.");
    }
    const liveSession = new GeminiLiveVoiceSession(
      {
        token: session.ephemeral_token,
        model: session.model,
        voiceName: session.voice_name ?? "Kore",
        onStatus: (status) => {
          if (status === "connecting") setVoiceChatStatus("connecting");
          if (status === "listening") setVoiceChatStatus("listening");
          if (status === "closed") {
            setVoiceChatMode("off");
            setVoiceChatStatus("idle");
          }
        },
        onError: () => {
          toast.error("Canlı sesli sohbet kesildi; normal sesli akışa geçtim.");
          void stopGeminiLiveVoice().then(startCascadeVoiceChat);
        },
      },
      async (message) => {
        const result = await sendMessage(message, { speakResponse: false });
        if (!result.ok || !result.assistantText.trim()) {
          throw new Error("Koç yanıtı hazırlanamadı.");
        }
        return result.assistantText;
      },
    );
    liveVoiceRef.current = liveSession;
    setVoiceChatMode("gemini-live");
    setVoiceChatStatus("connecting");
    await liveSession.start();
  }

  async function handleVoiceChat() {
    if (isHydrating || isTranscribing) return;
    dismissVoiceHint();
    if (voiceChatMode === "gemini-live") {
      await stopGeminiLiveVoice();
      return;
    }
    if (voiceChatMode === "cascade") {
      await stopCascadeVoiceChat();
      return;
    }
    try {
      const session = await api<VoiceSessionResponse>("/api/voice/session", {
        method: "POST",
        silent: true,
      });
      if (session.provider === "gemini" && session.mode === "realtime") {
        try {
          await startGeminiLiveVoice(session);
          return;
        } catch {
          await stopGeminiLiveVoice();
          toast.error("Canlı sesli sohbet açılamadı; normal sesli akışa geçtim.");
        }
      }
      await startCascadeVoiceChat();
    } catch {
      toast.error("Canlı sesli sohbet açılamadı; normal sesli akışa geçtim.");
      await startCascadeVoiceChat();
    }
  }

  function createRecognition(mode: VoiceInputMode): SpeechRecognitionLike | null {
    const SpeechRecognitionConstructorRef =
      window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!SpeechRecognitionConstructorRef) return null;
    recognitionRef.current?.abort();
    const recognition = new SpeechRecognitionConstructorRef();
    recognitionRef.current = recognition;
    recognition.lang = "tr-TR";
    recognition.interimResults = true;
    recognition.continuous = true;
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript?.trim() ?? "")
        .filter(Boolean)
        .join(" ")
        .trim();
      if (transcript) fallbackTranscriptRef.current = transcript;
    };
    recognition.onerror = (event) => {
      if (event.error === "aborted") return;
      if (mode === "browser") {
        setIsListening(false);
        setIsTranscribing(false);
        isTranscribingRef.current = false;
        activeVoiceModeRef.current = null;
        if (voiceChatModeRef.current === "cascade") {
          setVoiceChatStatus("listening");
          recoverCascadeListening(CASCADE_RESTART_DELAY_MS);
        } else {
          setVoiceChatMode((current) => (current === "cascade" ? "off" : current));
          toast.error("Ses alınamadı, tekrar dener misin?");
        }
      }
    };
    recognition.onend = () => {
      if (recognitionRef.current === recognition) recognitionRef.current = null;
      if (mode !== "browser" || activeVoiceModeRef.current !== "browser") return;
      setIsListening(false);
      setIsTranscribing(false);
      isTranscribingRef.current = false;
      activeVoiceModeRef.current = null;
      const fallbackTranscript = fallbackTranscriptRef.current.trim();
      fallbackTranscriptRef.current = "";
      if (fallbackTranscript) {
        void sendVoiceTranscript(
          fallbackTranscript,
          voiceChatModeRef.current === "cascade" ? "voice-chat" : "manual",
        );
        return;
      }
      if (voiceChatModeRef.current === "cascade" && cascadeVoiceActiveRef.current) {
        setVoiceChatStatus("listening");
        recoverCascadeListening(CASCADE_RESTART_DELAY_MS);
      } else {
        setVoiceChatMode((current) => (current === "cascade" ? "off" : current));
        toast.error("Ses alınamadı, tekrar dener misin?");
      }
    };
    return recognition;
  }

  async function handleRecordedAudio({
    chunks,
    contentType,
    sessionId,
    source = "manual",
  }: {
    chunks: Blob[];
    contentType: string;
    sessionId: number;
    source?: VoiceTranscriptSource;
  }) {
    try {
      if (sessionId !== voiceSessionRef.current) return;
      if (chunks.length === 0) throw new Error("Ses kaydı boş görünüyor.");
      const audio = new Blob(chunks, { type: contentType });
      if (source === "voice-chat" && audio.size < 4000) {
        throw new Error("Ses kaydı konuşma içermiyor.");
      }
      const formData = new FormData();
      formData.append("audio", audio, filenameForAudioType(contentType));
      const response = await api<{ text: string }>("/api/stt", {
        method: "POST",
        body: formData,
        silent: true,
      });
      setIsTranscribing(false);
      isTranscribingRef.current = false;
      const transcript = response.text.trim();
      if (!transcript) {
        throw new Error("Ses kaydı konuşma içermiyor.");
      }
      await sendVoiceTranscript(transcript, source);
    } catch (err) {
      const fallbackTranscript = fallbackTranscriptRef.current.trim();
      if (fallbackTranscript) {
        setIsTranscribing(false);
        isTranscribingRef.current = false;
        await sendVoiceTranscript(fallbackTranscript, source);
      } else {
        if (source === "voice-chat" && cascadeVoiceActiveRef.current) {
          setIsTranscribing(false);
          isTranscribingRef.current = false;
          activeVoiceModeRef.current = null;
          recoverCascadeListening();
        } else {
          toast.error(friendlyError(err, "Ses alınamadı, tekrar dener misin?"));
        }
      }
    } finally {
      if (sessionId !== voiceSessionRef.current) return;
      setIsTranscribing(false);
      isTranscribingRef.current = false;
      fallbackTranscriptRef.current = "";
      activeVoiceModeRef.current = null;
      recognitionRef.current = null;
      if (source !== "voice-chat") {
        setVoiceChatMode((current) => (current === "cascade" ? "off" : current));
      }
    }
  }

  async function startProviderVoiceInput() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error("Mikrofon kaydı başlatılamadı.");
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaStreamRef.current = stream;
    const mimeType = preferredRecordingMimeType();
    const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    const sessionId = voiceSessionRef.current + 1;
    voiceSessionRef.current = sessionId;
    activeVoiceModeRef.current = "provider";
    recordedChunksRef.current = [];
    fallbackTranscriptRef.current = "";
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) recordedChunksRef.current.push(event.data);
    };
    recorder.onstop = () => {
      const chunks = recordedChunksRef.current;
      const contentType = recorder.mimeType || chunks[0]?.type || "application/octet-stream";
      mediaRecorderRef.current = null;
      stopMediaStream(mediaStreamRef.current);
      mediaStreamRef.current = null;
      recordedChunksRef.current = [];
      void handleRecordedAudio({ chunks, contentType, sessionId });
    };
    recorder.onerror = () => {
      stopMediaStream(mediaStreamRef.current);
      mediaStreamRef.current = null;
      mediaRecorderRef.current = null;
      recordedChunksRef.current = [];
      fallbackTranscriptRef.current = "";
      setIsListening(false);
      setIsTranscribing(false);
      isTranscribingRef.current = false;
      activeVoiceModeRef.current = null;
      if (voiceChatModeRef.current === "cascade") {
        voicePauseReasonRef.current = "user";
        setVoicePauseReason("user");
        setVoiceChatStatus("idle");
      } else {
        setVoiceChatMode((current) => (current === "cascade" ? "off" : current));
        toast.error("Mikrofon kaydı başlatılamadı.");
      }
    };
    mediaRecorderRef.current = recorder;
    const backupRecognition = createRecognition("provider");
    try {
      backupRecognition?.start();
    } catch {
      recognitionRef.current = null;
    }
    recorder.start();
    setIsListening(true);
  }

  function startBrowserVoiceInput() {
    const recognition = createRecognition("browser");
    if (!recognition) {
      toast.error("Bu tarayıcı sesli giriş desteklemiyor.");
      return;
    }
    activeVoiceModeRef.current = "browser";
    fallbackTranscriptRef.current = "";
    try {
      setIsListening(true);
      recognition.start();
    } catch {
      setIsListening(false);
      if (voiceChatModeRef.current === "cascade") {
        voicePauseReasonRef.current = "user";
        setVoicePauseReason("user");
        setVoiceChatStatus("idle");
      } else {
        toast.error("Mikrofon başlatılamadı.");
      }
    }
  }

  function handleVoiceInput() {
    if (isStreaming || isHydrating || isTranscribing) return;
    if (isListening) {
      if (activeVoiceModeRef.current === "provider") {
        recognitionRef.current?.stop();
        mediaRecorderRef.current?.stop();
        setIsListening(false);
        setIsTranscribing(true);
        isTranscribingRef.current = true;
        return;
      }
      recognitionRef.current?.stop();
      setIsListening(false);
      setIsTranscribing(true);
      isTranscribingRef.current = true;
      return;
    }
    if (supportsProviderRecording) {
      void startProviderVoiceInput().catch(() => {
        stopMediaStream(mediaStreamRef.current);
        mediaStreamRef.current = null;
        mediaRecorderRef.current = null;
        recordedChunksRef.current = [];
        if (supportsBrowserSpeechInput) {
          startBrowserVoiceInput();
          return;
        }
        toast.error("Mikrofon başlatılamadı.");
      });
      return;
    }
    startBrowserVoiceInput();
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
    voiceSessionRef.current += 1;
    recognitionRef.current?.abort();
    mediaRecorderRef.current?.stop();
    stopMediaStream(mediaStreamRef.current);
    mediaRecorderRef.current = null;
    mediaStreamRef.current = null;
    recordedChunksRef.current = [];
    fallbackTranscriptRef.current = "";
    activeVoiceModeRef.current = null;
    setIsListening(false);
    setIsTranscribing(false);
    isTranscribingRef.current = false;
    void stopCascadeVoiceChat();
    void stopGeminiLiveVoice();
    stopActiveSpeech();
    rememberActiveConversationId(null);
  }

  const voiceChatTitle = voiceStatusTitle(voiceChatMode, voiceChatStatus);
  const voiceChatDescription = voiceStatusDescription(
    voiceChatMode,
    voiceChatStatus,
    voicePauseReason,
  );
  const showVoiceChatPanel = voiceChatMode !== "off";
  const canControlCascadeVoice = voiceChatMode === "cascade";
  const canStopVoiceResponse =
    voiceChatMode === "cascade" &&
    (voiceChatStatus === "synthesizing" || voiceChatStatus === "speaking" || isStreaming);
  const voiceMeterActive =
    voicePauseReason !== "user" &&
    (voiceChatStatus === "listening" ||
      voiceChatStatus === "recording" ||
      voiceChatStatus === "synthesizing" ||
      voiceChatStatus === "speaking");

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
                        onDecision={handleApprovalDecision}
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

      <div className="relative shrink-0">
        {showVoiceChatPanel ? (
          <section
            aria-label="Sesli koç oturumu"
            className="mb-2 rounded-[1.4rem] border border-primary/20 bg-card/85 px-3 py-3 shadow-sm"
          >
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "grid h-8 w-8 place-items-center rounded-full border border-primary/25 bg-primary/10 text-primary",
                      voiceMeterActive ? "animate-pulse" : "",
                    )}
                    aria-hidden="true"
                  >
                    <Headphones className="h-4 w-4" />
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-black leading-tight text-foreground">
                      {voiceChatTitle}
                    </p>
                    <p className="line-clamp-1 text-xs font-semibold text-muted-foreground">
                      {voiceChatDescription}
                    </p>
                  </div>
                </div>
              </div>

              <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">
                {canControlCascadeVoice ? (
                  <>
                    <Button
                      type="button"
                      variant={voicePauseReason === "user" ? "default" : "outline"}
                      size="sm"
                      onClick={() => setCascadeUserPaused(voicePauseReason !== "user")}
                      className="h-9 rounded-full px-3"
                    >
                      {voicePauseReason === "user" ? (
                        <Mic className="h-4 w-4" />
                      ) : (
                        <MicOff className="h-4 w-4" />
                      )}
                      <span className="hidden sm:inline">
                        {voicePauseReason === "user" ? "Mikrofonu aç" : "Mikrofonu kapat"}
                      </span>
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={!canStopVoiceResponse}
                      onClick={stopVoiceResponse}
                      className="h-9 rounded-full px-3"
                    >
                      <Square className="h-4 w-4" />
                      <span className="hidden sm:inline">Yanıtı durdur</span>
                    </Button>
                  </>
                ) : null}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  aria-label="Sesli koç oturumunu kapat"
                  onClick={() => {
                    if (voiceChatMode === "gemini-live") {
                      void stopGeminiLiveVoice();
                    } else {
                      void stopCascadeVoiceChat();
                    }
                  }}
                  className="h-9 w-9 rounded-full px-0"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </section>
        ) : null}

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
              <span>
                {showVoiceChatPanel
                  ? voiceChatTitle
                  : isTranscribing
                    ? "Ses yazıya çevriliyor..."
                    : isListening
                      ? "Dinliyorum..."
                      : "Mikrofon hazır"}
              </span>
            ) : null}
          </div>
          <div
            className={cn(
              "grid gap-2",
              supportsSpeechInput
                ? "grid-cols-[2.75rem_2.75rem_2.75rem_minmax(0,1fr)_2.75rem]"
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
                  aria-label={
                    isTranscribing
                      ? "Ses yazıya çevriliyor"
                      : isListening
                        ? "Ses kaydını durdur"
                        : "Sesli yaz"
                  }
                  disabled={isStreaming || isHydrating || isTranscribing || voiceChatMode !== "off"}
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
                    <span className="block leading-snug">
                      Mikrofona dokun, koça sesli soru sor.
                    </span>
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
            {supportsSpeechInput ? (
              <button
                type="button"
                aria-label={
                  voiceChatMode === "gemini-live"
                    ? "Canlı sesli sohbeti kapat"
                    : voiceChatMode === "cascade" && isListening
                      ? "Sesli sohbet kaydını durdur"
                      : "Sesli sohbet başlat"
                }
                disabled={
                  isHydrating ||
                  (voiceChatMode === "off" && (isStreaming || isTranscribing)) ||
                  (isListening && voiceChatMode === "off")
                }
                onClick={() => void handleVoiceChat()}
                className={cn(
                  "inline-flex h-11 w-11 items-center justify-center rounded-full border border-border bg-background/70 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground disabled:pointer-events-none disabled:opacity-50",
                  voiceChatMode !== "off" ? "border-primary bg-primary/10 text-primary" : "",
                )}
              >
                {voiceChatStatus === "connecting" || voiceChatStatus === "thinking" ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Headphones className="h-4 w-4" />
                )}
              </button>
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
    </div>
  );
}
