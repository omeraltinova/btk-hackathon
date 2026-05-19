"use client";

import {
  ArrowLeft,
  Bot,
  Download,
  FileText,
  Loader2,
  MessageSquareText,
  Play,
  Trash2,
  User as UserIcon,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import { ChatChart } from "@/components/ChatChart";
import { FormattedMessageContent } from "@/components/ChatMessage";
import { Button } from "@/components/ui/button";
import { ACTIVE_PROFILE_EVENT } from "@/lib/active-profile";
import { api, ApiError, apiDownload } from "@/lib/api";
import { chatAttachmentsFromHistory, type ChatAttachmentItem } from "@/lib/chat-attachments";
import { readActiveConversationId, rememberActiveConversationId } from "@/lib/chat-session";
import { formatDateTR } from "@/lib/format";
import type { ConversationListItem, ConversationMessages } from "@/lib/types";
import { cn } from "@/lib/utils";

function friendlyError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  return `${formatDateTR(value)} ${new Intl.DateTimeFormat("tr-TR", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Istanbul",
  }).format(date)}`;
}

function RoleBadge({ role, toolName }: { role: string; toolName: string | null }) {
  if (role === "user") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2 py-0.5 text-[0.7rem] font-bold text-primary">
        <UserIcon className="h-3 w-3" />
        Sen
      </span>
    );
  }
  if (role === "assistant") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-accent/30 px-2 py-0.5 text-[0.7rem] font-bold text-accent-foreground">
        <Bot className="h-3 w-3" />
        Koç
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[0.7rem] font-bold text-muted-foreground">
      <Wrench className="h-3 w-3" />
      Araç {toolName ? `· ${toolName}` : ""}
    </span>
  );
}

function renderHistoryAttachment(attachment: ChatAttachmentItem) {
  if (attachment.type === "chart") {
    return <ChatChart key={attachment.id} spec={attachment.spec} />;
  }
  if (attachment.type === "report") {
    return <HistoryReportAttachment key={attachment.id} attachment={attachment} />;
  }
  return (
    <figure
      key={attachment.id}
      className="mt-2 overflow-hidden rounded-2xl border border-border/70 bg-card/85 shadow-sm"
    >
      {/* eslint-disable-next-line @next/next/no-img-element -- Historical chat images are user-scoped MinIO URLs. */}
      <img
        src={attachment.imageUrl}
        alt={attachment.altText}
        className="max-h-80 w-full object-cover"
      />
      <figcaption className="px-3 py-2 text-xs font-medium text-muted-foreground">
        {attachment.altText}
      </figcaption>
    </figure>
  );
}

function HistoryReportAttachment({
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
    <section className="cash-envelope mt-2 overflow-hidden px-4 py-4 shadow-sm">
      <div className="relative z-10 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="bg-primary/12 grid h-10 w-10 shrink-0 place-items-center rounded-2xl text-primary">
            <FileText className="h-5 w-5" />
          </span>
          <div>
            <p className="eyebrow">DOCX rapor</p>
            <h4 className="mt-1 font-display text-lg font-black tracking-tight">
              {attachment.title}
            </h4>
            <p className="mt-1 text-xs font-semibold text-muted-foreground">
              {attachment.filename}
            </p>
          </div>
        </div>
        <Button type="button" size="sm" onClick={handleDownload} disabled={isDownloading}>
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

export function ChatHistoryClient() {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [thread, setThread] = useState<ConversationMessages | null>(null);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingThread, setIsLoadingThread] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadConversations = useCallback(async () => {
    setError(null);
    try {
      const data = await api<ConversationListItem[]>("/api/conversations", { silent: true });
      setConversations(data);
      const first = data[0];
      setSelectedId((current) => current ?? first?.id ?? null);
    } catch (err) {
      setError(friendlyError(err, "Geçmiş sohbetler yüklenemedi."));
    } finally {
      setIsLoadingList(false);
    }
  }, []);

  useEffect(() => {
    void loadConversations();
    function reload() {
      setSelectedId(null);
      setThread(null);
      setIsLoadingList(true);
      void loadConversations();
    }
    window.addEventListener(ACTIVE_PROFILE_EVENT, reload);
    return () => window.removeEventListener(ACTIVE_PROFILE_EVENT, reload);
  }, [loadConversations]);

  useEffect(() => {
    if (selectedId === null) {
      setThread(null);
      return;
    }
    let cancelled = false;
    setIsLoadingThread(true);
    void (async () => {
      try {
        const data = await api<ConversationMessages>(`/api/conversations/${selectedId}/messages`, {
          silent: true,
        });
        if (!cancelled) setThread(data);
      } catch (err) {
        if (!cancelled) setError(friendlyError(err, "Sohbet mesajları yüklenemedi."));
      } finally {
        if (!cancelled) setIsLoadingThread(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const selectedConversation = conversations.find((conversation) => conversation.id === selectedId);

  async function handleDeleteConversation(conversationId: string) {
    if (!window.confirm("Bu sohbeti kalıcı olarak silmek istediğine emin misin?")) return;
    setDeletingId(conversationId);
    setError(null);
    try {
      await api<void>(`/api/conversations/${conversationId}`, {
        method: "DELETE",
        silent: true,
      });
      setConversations((current) => {
        const next = current.filter((conversation) => conversation.id !== conversationId);
        if (selectedId === conversationId) {
          setSelectedId(next[0]?.id ?? null);
          setThread(null);
        }
        if (readActiveConversationId() === conversationId) {
          rememberActiveConversationId(null);
        }
        return next;
      });
    } catch (err) {
      setError(friendlyError(err, "Sohbet silinemedi."));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="flex h-[calc(100svh-9.5rem)] min-h-0 flex-col gap-3 overflow-hidden sm:h-[calc(100svh-8.5rem)] lg:h-[calc(100svh-8rem)]">
      <header className="ledger-sheet p-4">
        <div className="relative z-10 flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="eyebrow">Koç ile arşiv</p>
            <h1 className="mt-1 font-display text-2xl font-black tracking-[-0.04em] sm:text-3xl">
              Sohbet geçmişin
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span className="rounded-full bg-background/70 px-3 py-1 font-semibold">
              {conversations.length} sohbet
            </span>
            {selectedId ? (
              <Button asChild size="sm" className="rounded-[1rem]">
                <Link href="/chat" onClick={() => rememberActiveConversationId(selectedId)}>
                  <Play className="h-4 w-4" />
                  Bu sohbeti sürdür
                </Link>
              </Button>
            ) : null}
            <Button asChild variant="outline" size="sm" className="rounded-[1rem]">
              <Link href="/chat">
                <ArrowLeft className="h-4 w-4" />
                Sohbete dön
              </Link>
            </Button>
          </div>
        </div>
        <p className="relative z-10 mt-2 max-w-3xl text-xs leading-5 text-muted-foreground sm:text-sm">
          Bu arşiv yalnızca aktif profilindir. Çocuk sohbetleri için önce aile sayfasından o profile
          geç.
        </p>
      </header>

      {error ? (
        <p className="bg-destructive/14 rounded-2xl border border-destructive/35 px-4 py-2 text-sm font-semibold text-foreground shadow-sm">
          {error}
        </p>
      ) : null}

      <div className="grid min-h-0 min-w-0 flex-1 gap-3 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <aside className="flex max-h-56 min-h-0 flex-col rounded-[1.75rem] border border-border/70 bg-card/80 p-2 shadow-sm lg:max-h-none">
          <div className="flex items-center justify-between gap-2 px-2 py-1.5">
            <p className="eyebrow">Sohbetler</p>
            {isLoadingList ? <Loader2 className="h-4 w-4 animate-spin text-primary" /> : null}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto pr-1">
            {isLoadingList ? (
              <div className="flex items-center gap-2 rounded-2xl bg-background/65 px-3 py-3 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Yükleniyor...
              </div>
            ) : conversations.length === 0 ? (
              <div className="rounded-2xl bg-background/65 px-4 py-5">
                <MessageSquareText className="h-5 w-5 text-primary" />
                <h3 className="mt-2 font-display text-lg font-black">Henüz sohbet yok</h3>
                <p className="mt-1 text-sm leading-6 text-muted-foreground">
                  Koçla ilk konuştuğunda burada kısa bir satır olarak görünür.
                </p>
              </div>
            ) : (
              <ul className="space-y-1.5">
                {conversations.map((conversation) => {
                  const isActive = conversation.id === selectedId;
                  const stamp = conversation.last_message_at ?? conversation.started_at;
                  return (
                    <li key={conversation.id}>
                      <div
                        className={cn(
                          "grid grid-cols-[minmax(0,1fr)_auto] items-center gap-1 rounded-2xl border p-1 transition-colors",
                          isActive
                            ? "bg-primary/12 border-primary/55"
                            : "border-transparent hover:border-border/80 hover:bg-background/70",
                        )}
                      >
                        <button
                          type="button"
                          onClick={() => setSelectedId(conversation.id)}
                          className="min-w-0 rounded-[1.05rem] px-2 py-1.5 text-left"
                        >
                          <div className="flex items-center justify-between gap-2 text-[0.7rem] text-muted-foreground">
                            <span className="min-w-0 truncate">{formatDateTime(stamp)}</span>
                            <span className="shrink-0 rounded-full bg-background/75 px-2 py-0.5 font-bold">
                              {conversation.message_count}
                            </span>
                          </div>
                          <p className="mt-1 line-clamp-1 text-sm font-semibold">
                            {conversation.preview || "Sohbet başlığı yok"}
                          </p>
                        </button>
                        <div className="flex items-center gap-1 pr-1">
                          <Link
                            href="/chat"
                            onClick={() => rememberActiveConversationId(conversation.id)}
                            aria-label="Bu sohbeti sürdür"
                            className="grid h-8 w-8 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-primary hover:text-primary-foreground"
                          >
                            <Play className="h-3.5 w-3.5" />
                          </Link>
                          <button
                            type="button"
                            aria-label="Sohbeti sil"
                            onClick={() => void handleDeleteConversation(conversation.id)}
                            disabled={deletingId === conversation.id}
                            className="grid h-8 w-8 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-destructive/15 hover:text-destructive disabled:opacity-50"
                          >
                            {deletingId === conversation.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="h-3.5 w-3.5" />
                            )}
                          </button>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </aside>

        <section className="ledger-sheet flex min-h-0 flex-col p-4">
          <div className="relative z-10 flex flex-wrap items-center justify-between gap-3 border-b border-border/70 pb-3">
            <div className="min-w-0">
              <p className="eyebrow">Seçili kayıt</p>
              <h2 className="mt-1 truncate font-display text-2xl font-black tracking-[-0.04em]">
                {selectedConversation?.preview || "Sohbet detayı"}
              </h2>
            </div>
            {selectedConversation ? (
              <span className="rounded-full bg-background/70 px-3 py-1 text-xs font-bold text-muted-foreground">
                {selectedConversation.message_count} mesaj
              </span>
            ) : null}
          </div>

          <div className="relative z-10 min-h-0 flex-1 overflow-y-auto pt-3">
            {isLoadingThread ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Mesajlar yükleniyor...
              </div>
            ) : thread === null ? (
              <p className="text-sm text-muted-foreground">Soldaki bir sohbeti seç.</p>
            ) : thread.messages.length === 0 ? (
              <p className="text-sm text-muted-foreground">Bu sohbette mesaj yok.</p>
            ) : (
              <ol className="space-y-2">
                {thread.messages.map((message) => {
                  const attachments = chatAttachmentsFromHistory(message.attachments).map(
                    (attachment) => ({
                      ...attachment,
                      id: `${message.id}-${attachment.id}`,
                    }),
                  );
                  return (
                    <li
                      key={message.id}
                      className={cn(
                        "rounded-2xl border px-3 py-2",
                        message.role === "tool"
                          ? "border-border/40 bg-muted/45"
                          : "bg-background/62 border-border/60",
                      )}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <RoleBadge role={message.role} toolName={message.tool_name} />
                        <span className="text-[0.7rem] text-muted-foreground">
                          {formatDateTime(message.created_at)}
                        </span>
                      </div>
                      <div className="mt-1 space-y-3 text-sm leading-6">
                        <FormattedMessageContent content={message.content} />
                      </div>
                      {attachments.length > 0 ? (
                        <div className="mt-3 space-y-3">
                          {attachments.map(renderHistoryAttachment)}
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ol>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
