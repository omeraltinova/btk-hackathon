"use client";

import { WalletCards } from "lucide-react";
import type { ReactNode } from "react";

type InsightBannerProps = {
  title: string;
  children: ReactNode;
  label?: string;
};

export function InsightBanner({ title, children, label = "Koç notu" }: InsightBannerProps) {
  return (
    <aside className="receipt-tape p-5 pt-8 text-sm leading-6 text-foreground sm:p-6 sm:pt-9">
      <p className="font-display text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">
        {label}
      </p>
      <div className="mt-5 flex items-start gap-3">
        <span className="pulse-soft grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent text-accent-foreground">
          <WalletCards className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <h2 className="font-display text-[1.65rem] font-black leading-7 sm:text-2xl">{title}</h2>
          <div className="text-foreground/78 mt-3">{children}</div>
        </div>
      </div>
    </aside>
  );
}
