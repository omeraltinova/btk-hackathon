const ACTIVE_CONVERSATION_KEY = "cuzdan-kocu.chat.active-conversation";
const PENDING_CHAT_MESSAGE_KEY = "cuzdan-kocu.chat.pending-message";
const PENDING_MESSAGE_MAX_AGE_MS = 5 * 60 * 1000;

export type PendingChatMessage = {
  message: string;
  source: "learn" | "dashboard";
  title?: string;
  startNew?: boolean;
  createdAt: number;
};

export function readActiveConversationId(): string | null {
  try {
    return window.sessionStorage.getItem(ACTIVE_CONVERSATION_KEY);
  } catch {
    return null;
  }
}

export function rememberActiveConversationId(conversationId: string | null) {
  try {
    if (conversationId) {
      window.sessionStorage.setItem(ACTIVE_CONVERSATION_KEY, conversationId);
    } else {
      window.sessionStorage.removeItem(ACTIVE_CONVERSATION_KEY);
    }
  } catch {
    // Session storage can be unavailable in strict browser privacy modes.
  }
}

export function rememberPendingChatMessage(payload: Omit<PendingChatMessage, "createdAt">): void {
  try {
    window.sessionStorage.setItem(
      PENDING_CHAT_MESSAGE_KEY,
      JSON.stringify({ ...payload, createdAt: Date.now() }),
    );
  } catch {
    // Session storage can be unavailable in strict browser privacy modes.
  }
}

export function clearPendingChatMessage(): void {
  try {
    window.sessionStorage.removeItem(PENDING_CHAT_MESSAGE_KEY);
  } catch {
    // Session storage can be unavailable in strict browser privacy modes.
  }
}

export function readPendingChatMessage(): PendingChatMessage | null {
  try {
    const raw = window.sessionStorage.getItem(PENDING_CHAT_MESSAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") {
      clearPendingChatMessage();
      return null;
    }
    const candidate = parsed as Partial<PendingChatMessage>;
    if (
      typeof candidate.message !== "string" ||
      candidate.message.trim().length === 0 ||
      (candidate.source !== "learn" && candidate.source !== "dashboard") ||
      typeof candidate.createdAt !== "number"
    ) {
      clearPendingChatMessage();
      return null;
    }
    if (Date.now() - candidate.createdAt > PENDING_MESSAGE_MAX_AGE_MS) {
      clearPendingChatMessage();
      return null;
    }
    return {
      message: candidate.message,
      source: candidate.source,
      title: typeof candidate.title === "string" ? candidate.title : undefined,
      startNew: Boolean(candidate.startNew),
      createdAt: candidate.createdAt,
    };
  } catch {
    clearPendingChatMessage();
    return null;
  }
}
