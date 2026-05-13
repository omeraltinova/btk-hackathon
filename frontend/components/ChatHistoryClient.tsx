"use client";

import { ArrowLeft, Bot, Loader2, MessageSquareText, User as UserIcon, Wrench } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { ACTIVE_PROFILE_EVENT } from "@/lib/active-profile";
import { api, ApiError } from "@/lib/api";
import { formatDateTR } from "@/lib/format";
import type { ConversationListItem, ConversationMessages } from "@/lib/types";

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
      <span className="inline-flex items-center gap-1 rounded-full bg-primary/15 px-2.5 py-1 text-xs font-bold text-primary">
        <UserIcon className="h-3 w-3" />
        Sen
      </span>
    );
  }
  if (role === "assistant") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-accent/30 px-2.5 py-1 text-xs font-bold text-accent-foreground">
        <Bot className="h-3 w-3" />
        Koç
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-xs font-bold text-muted-foreground">
      <Wrench className="h-3 w-3" />
      Araç {toolName ? `· ${toolName}` : ""}
    </span>
  );
}

export function ChatHistoryClient() {
  const [conversations, setConversations] = useState<ConversationListItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [thread, setThread] = useState<ConversationMessages | null>(null);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingThread, setIsLoadingThread] = useState(false);
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

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Koç ile arşiv</p>
          <h1 className="mt-2 font-display text-3xl font-black tracking-[-0.04em] sm:text-4xl">
            Sohbet geçmişin
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Sadece bu profilin sohbetleri listelenir. Ebeveyn olarak çocuğun sohbetini görmek için
            aile sayfasından çocuk profiline geçmen gerekir.
          </p>
        </div>
        <Button asChild variant="outline">
          <Link href="/chat">
            <ArrowLeft className="h-4 w-4" />
            Yeni sohbet
          </Link>
        </Button>
      </header>

      {error ? (
        <p className="bg-destructive/14 rounded-2xl border border-destructive/35 px-4 py-3 text-sm font-semibold text-foreground shadow-sm">
          {error}
        </p>
      ) : null}

      <div className="grid min-w-0 gap-5 lg:grid-cols-[0.7fr_1.3fr]">
        <aside className="space-y-3">
          <p className="eyebrow">Sohbetler</p>
          {isLoadingList ? (
            <div className="receipt-tape flex items-center gap-2 px-4 py-4 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Yükleniyor...
            </div>
          ) : conversations.length === 0 ? (
            <div className="receipt-tape px-5 py-8">
              <MessageSquareText className="h-6 w-6 text-primary" />
              <h3 className="mt-3 font-display text-xl font-black">Henüz sohbet yok</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Koçla ilk konuştuğunda buraya kaydedilir.
              </p>
            </div>
          ) : (
            <ul className="space-y-2">
              {conversations.map((conversation) => {
                const isActive = conversation.id === selectedId;
                const stamp = conversation.last_message_at ?? conversation.started_at;
                return (
                  <li key={conversation.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(conversation.id)}
                      className={
                        "w-full rounded-2xl border px-4 py-3 text-left transition-all duration-200 ease-quint hover:-translate-y-0.5 " +
                        (isActive
                          ? "bg-primary/12 border-primary/60 shadow-md"
                          : "border-border/70 bg-card/80 hover:border-primary/30")
                      }
                    >
                      <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                        <span>{formatDateTime(stamp)}</span>
                        <span className="font-bold">{conversation.message_count} mesaj</span>
                      </div>
                      <p className="mt-2 line-clamp-2 text-sm font-medium">
                        {conversation.preview || "Sohbet başlığı yok"}
                      </p>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </aside>

        <section className="ledger-sheet min-h-72 p-5 sm:p-7">
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
            <ol className="relative z-10 space-y-4">
              {thread.messages.map((message) => (
                <li
                  key={message.id}
                  className="rounded-2xl border border-border/60 bg-background/60 px-4 py-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <RoleBadge role={message.role} toolName={message.tool_name} />
                    <span className="text-xs text-muted-foreground">
                      {formatDateTime(message.created_at)}
                    </span>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{message.content}</p>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}
