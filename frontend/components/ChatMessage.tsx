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
    <div className={cn("flex items-start gap-3", isAssistant ? "justify-start" : "justify-end")}>
      {isAssistant ? (
        <span className="mt-2 grid h-10 w-10 shrink-0 place-items-center rounded-[1rem_1rem_0.5rem_1rem] bg-primary text-primary-foreground">
          <Icon className="h-4 w-4" />
        </span>
      ) : null}
      <div
        className={cn(
          "min-w-0 break-words text-left text-sm leading-6",
          isAssistant
            ? "receipt-tape max-w-[44rem] px-5 pb-5 pt-5 text-foreground sm:px-6"
            : "hard-shadow-accent max-w-[88%] rounded-[1.4rem_1.4rem_0.65rem_1.4rem] bg-primary px-4 py-3 text-primary-foreground sm:max-w-[82%]",
        )}
      >
        <p className="font-semibold leading-none">{label}</p>
        <p className="mt-2 max-w-prose whitespace-pre-wrap text-left opacity-85">
          {content || (isStreaming ? "Yanıt hazırlanıyor..." : "")}
        </p>
        {children ? <div className="mt-4 space-y-3">{children}</div> : null}
      </div>
    </div>
  );
}
