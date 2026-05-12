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
    <aside className="receipt-tape p-6 pt-9 text-sm leading-6 text-foreground">
      <p className="font-display text-xs font-bold uppercase tracking-[0.24em] text-muted-foreground">
        {label}
      </p>
      <div className="mt-5 flex items-start gap-3">
        <span className="pulse-soft grid h-10 w-10 shrink-0 place-items-center rounded-full bg-accent text-accent-foreground">
          <WalletCards className="h-5 w-5" />
        </span>
        <div>
          <h2 className="font-display text-2xl font-black leading-7">{title}</h2>
          <div className="mt-3 text-muted-foreground">{children}</div>
        </div>
      </div>
    </aside>
  );
}
