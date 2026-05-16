"use client";

import { Bot, UserRound, Volume2 } from "lucide-react";
import { Fragment, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type ChatMessageProps = {
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
  children?: ReactNode;
};

function renderInlineMarkdown(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const inlinePattern = /!\[[^\]]*]\([^)]+\)|\*\*([^*]+?)\*\*|\*([^*]+?)\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = inlinePattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    if (match[0].startsWith("![")) {
      nodes.push("");
    } else if (match[1]) {
      nodes.push(
        <strong key={`${keyPrefix}-${match.index}`} className="font-black">
          {match[1]}
        </strong>,
      );
    } else if (match[2]) {
      nodes.push(
        <em key={`${keyPrefix}-${match.index}`} className="font-semibold italic">
          {match[2]}
        </em>,
      );
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }

  return nodes.length > 0 ? nodes : [text];
}

function isBulletLine(line: string): boolean {
  return /^\s*[-*]\s+/.test(line);
}

function isOrderedLine(line: string): boolean {
  return /^\s*\d+\.\s+/.test(line);
}

function isDividerLine(line: string): boolean {
  return /^\s*(?:-{3,}|\*{3,})\s*$/.test(line);
}

function isMarkdownImageLine(line: string): boolean {
  return /^\s*!\[[^\]]*]\([^)]+\)\s*$/.test(line);
}

function stripBullet(line: string): string {
  return line.replace(/^\s*[-*]\s+/, "").trim();
}

function stripOrderedMarker(line: string): string {
  return line.replace(/^\s*\d+\.\s+/, "").trim();
}

function renderParagraph(lines: string[], key: string) {
  return (
    <p key={key}>
      {lines.map((line, index) => (
        <Fragment key={`${key}-${index}`}>
          {renderInlineMarkdown(line, `${key}-${index}`)}
          {index < lines.length - 1 ? <br /> : null}
        </Fragment>
      ))}
    </p>
  );
}

function renderList(items: string[], kind: "ordered" | "unordered", key: string) {
  const ListTag = kind === "ordered" ? "ol" : "ul";
  return (
    <ListTag
      key={key}
      className={cn(kind === "ordered" ? "list-decimal" : "list-disc", "space-y-2 ps-5")}
    >
      {items.map((item, index) => (
        <li key={`${key}-${index}`}>{renderInlineMarkdown(item, `${key}-${index}`)}</li>
      ))}
    </ListTag>
  );
}

function renderBlock(block: string, blockIndex: number): ReactNode[] {
  const elements: ReactNode[] = [];
  const lines = block
    .split("\n")
    .map((line) => line.trimEnd())
    .filter((line) => line.trim().length > 0 && !isMarkdownImageLine(line));
  let paragraphLines: string[] = [];
  let listItems: string[] = [];
  let listKind: "ordered" | "unordered" | null = null;

  function flushParagraph() {
    if (paragraphLines.length === 0) return;
    elements.push(renderParagraph(paragraphLines, `p-${blockIndex}-${elements.length}`));
    paragraphLines = [];
  }

  function flushList() {
    if (listItems.length === 0) return;
    elements.push(
      renderList(listItems, listKind ?? "unordered", `list-${blockIndex}-${elements.length}`),
    );
    listItems = [];
    listKind = null;
  }

  for (const line of lines) {
    const heading = line.match(/^\s*#{2,4}\s+(.+)$/);
    if (heading) {
      const headingText = heading[1] ?? "";
      flushParagraph();
      flushList();
      elements.push(
        <h3
          key={`h-${blockIndex}-${elements.length}`}
          className="pt-1 font-display text-lg font-black tracking-tight"
        >
          {renderInlineMarkdown(headingText.trim(), `h-${blockIndex}-${elements.length}`)}
        </h3>,
      );
      continue;
    }

    if (isDividerLine(line)) {
      flushParagraph();
      flushList();
      elements.push(
        <hr key={`hr-${blockIndex}-${elements.length}`} className="border-border/70" />,
      );
      continue;
    }

    if (isBulletLine(line)) {
      flushParagraph();
      if (listKind === "ordered") flushList();
      listKind = "unordered";
      listItems.push(stripBullet(line));
      continue;
    }

    if (isOrderedLine(line)) {
      flushParagraph();
      if (listKind === "unordered") flushList();
      listKind = "ordered";
      listItems.push(stripOrderedMarker(line));
      continue;
    }

    if (listItems.length > 0) {
      const lastItem = listItems[listItems.length - 1] ?? "";
      listItems[listItems.length - 1] = `${lastItem} ${line.trim()}`;
      continue;
    }

    paragraphLines.push(line);
  }

  flushParagraph();
  flushList();

  return elements;
}

export function FormattedMessageContent({ content }: { content: string }) {
  const blocks = content
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);

  return <>{blocks.flatMap((block, index) => renderBlock(block, index))}</>;
}

function speechTextFromMarkdown(content: string): string {
  return content
    .replace(/!\[[^\]]*]\([^)]+\)/g, "")
    .replace(/\[([^\]]+)]\([^)]+\)/g, "$1")
    .replace(/^\s*#{1,6}\s+/gm, "")
    .replace(/^\s*(?:[-*]|\d+\.)\s+/gm, "")
    .replace(/[*_`>]/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function speakMessage(content: string) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
  const speechText = speechTextFromMarkdown(content);
  if (!speechText) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(speechText);
  utterance.lang = "tr-TR";
  window.speechSynthesis.speak(utterance);
}

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
            ? "receipt-tape w-full max-w-[44rem] px-5 pb-5 pt-5 text-foreground sm:px-6 lg:max-w-[58rem] xl:max-w-[68rem]"
            : "hard-shadow-accent max-w-[88%] rounded-[1.4rem_1.4rem_0.65rem_1.4rem] bg-primary px-4 py-3 text-primary-foreground sm:max-w-[82%]",
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <p className="font-semibold leading-none">{label}</p>
          {isAssistant && content.trim() ? (
            <button
              type="button"
              title="Sesli oku"
              aria-label="Yanıtı sesli oku"
              onClick={() => speakMessage(content)}
              className="grid h-8 w-8 shrink-0 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <Volume2 className="h-4 w-4" />
            </button>
          ) : null}
        </div>
        <div
          className={cn(
            "mt-3 max-w-none space-y-4 text-left opacity-85",
            isAssistant ? "text-[0.95rem] leading-7" : "text-sm leading-6",
          )}
        >
          <FormattedMessageContent
            content={content || (isStreaming ? "Yanıt hazırlanıyor..." : "")}
          />
        </div>
        {children ? <div className="mt-5 space-y-3">{children}</div> : null}
      </div>
    </div>
  );
}
