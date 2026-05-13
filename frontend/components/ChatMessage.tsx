"use client";

import { Bot, UserRound } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type ChatMessageProps = {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  children?: ReactNode;
};

export function ChatMessage({ role, content, isStreaming = false, children }: ChatMessageProps) {
  const isAssistant = role === "assistant";
  const label = isAssistant ? "Cüzdan Koçu" : "Sen";
  const Icon = isAssistant ? Bot : UserRound;

  return (
    <div className={cn("flex gap-3", isAssistant ? "justify-start" : "justify-end")}>
      {isAssistant ? (
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-[1rem_1rem_0.5rem_1rem] bg-primary text-primary-foreground">
          <Icon className="h-4 w-4" />
        </span>
      ) : null}
      <div
        className={cn(
          "max-w-[88%] break-words px-4 py-3 text-sm leading-6 sm:max-w-[82%]",
          isAssistant
            ? "receipt-tape rotate-[-0.5deg] text-foreground"
            : "hard-shadow-accent rounded-[1.4rem_1.4rem_0.65rem_1.4rem] bg-primary text-primary-foreground",
        )}
      >
        <p className="font-semibold">{label}</p>
        <p className="mt-1 whitespace-pre-wrap opacity-85">
          {content || (isStreaming ? "Yanıt hazırlanıyor..." : "")}
        </p>
        {children ? <div className="mt-4 space-y-3">{children}</div> : null}
      </div>
    </div>
  );
}
