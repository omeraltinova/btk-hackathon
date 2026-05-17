import { getBackendToken } from "@/lib/active-profile";
import type { ChatStreamEvent, ChatStreamRequest } from "@/lib/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type StreamOptions = {
  signal?: AbortSignal;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isChatStreamEvent(value: unknown): value is ChatStreamEvent {
  if (!isRecord(value) || typeof value.type !== "string") return false;
  if (typeof value.conversation_id !== "string") return false;
  if (value.type === "message_start") return value.role === "assistant";
  if (value.type === "tool_call") {
    return typeof value.tool_name === "string" && isRecord(value.input);
  }
  if (value.type === "tool_result") {
    return typeof value.tool_name === "string" && isRecord(value.result);
  }
  if (value.type === "image") {
    return typeof value.image_url === "string" && typeof value.alt_text === "string";
  }
  if (value.type === "approval_required") {
    return (
      typeof value.approval_id === "string" &&
      typeof value.tool_name === "string" &&
      typeof value.action_label === "string" &&
      typeof value.summary === "string" &&
      Array.isArray(value.details) &&
      value.details.every((item) => typeof item === "string") &&
      isRecord(value.input)
    );
  }
  if (value.type === "delta") return typeof value.content === "string";
  return value.type === "done";
}

function parseSseBlock(block: string): ChatStreamEvent | null {
  const data = block
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart())
    .join("\n");
  if (!data) return null;

  try {
    const parsed: unknown = JSON.parse(data);
    return isChatStreamEvent(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

async function responseError(response: Response): Promise<Error> {
  try {
    const payload: unknown = await response.json();
    if (isRecord(payload) && typeof payload.detail === "string") {
      return new Error(payload.detail);
    }
  } catch {
    // Fall through to the generic Turkish message below.
  }
  return new Error("Koç akışı başlatılamadı, tekrar dener misin?");
}

export async function streamChat(
  payload: ChatStreamRequest,
  onEvent: (event: ChatStreamEvent) => void,
  options: StreamOptions = {},
): Promise<void> {
  const token = await getBackendToken(true);
  if (!token) throw new Error("Oturum bulunamadı, tekrar giriş yap.");

  const response = await fetch(`${BASE_URL}/api/chat/stream`, {
    method: "POST",
    headers: {
      Accept: "text/event-stream",
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
    signal: options.signal,
  });

  if (!response.ok) throw await responseError(response);
  if (!response.body) throw new Error("Koç akışı okunamadı, tekrar dener misin?");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const event = parseSseBlock(block);
      if (event) onEvent(event);
    }
  }

  buffer += decoder.decode();
  const finalEvent = parseSseBlock(buffer);
  if (finalEvent) onEvent(finalEvent);
}
