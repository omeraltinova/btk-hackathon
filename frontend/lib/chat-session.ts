const ACTIVE_CONVERSATION_KEY = "cuzdan-kocu.chat.active-conversation";

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
