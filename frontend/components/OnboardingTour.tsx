"use client";

import {
  ArrowRight,
  BookOpen,
  MessageSquare,
  ReceiptText,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import Link from "next/link";
import { type ReactNode, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "cuzdan-kocu.onboarding-tour";

type Step = {
  eyebrow: string;
  title: string;
  body: string;
  icon: ReactNode;
  ctaLabel?: string;
  ctaHref?: string;
};

const STEPS: Step[] = [
  {
    eyebrow: "Hoş geldin",
    title: "Cüzdan Koçu'nun mini turuna hazır mısın?",
    body: "30 saniyede uygulamanın 4 ana parçasını gezeceğiz: işlemler, koç sohbeti, hedefler ve dersler. İstediğin an atlayabilirsin.",
    icon: <Sparkles className="h-6 w-6 text-primary" />,
  },
  {
    eyebrow: "1. İşlemler",
    title: "Gelir, gider ve fiş tek yerde toplanır",
    body: "Tek seferlik harcamayı, tekrarlayan ödemeyi veya bir fişin fotoğrafını İşlemler ekranından girersin. OCR fişi otomatik kategorize eder.",
    icon: <ReceiptText className="h-6 w-6 text-primary" />,
    ctaLabel: "İşlemlere git",
    ctaHref: "/transactions",
  },
  {
    eyebrow: "2. Koç sohbeti",
    title: "Soru sor — koç verine bakarak cevaplar",
    body: "Sohbette 'Bu ay markete ne kadar harcadım?', 'Hedeflerimi göster' gibi sorular yazabilirsin. Koç senin verine erişir, başkasınınkine değil.",
    icon: <MessageSquare className="h-6 w-6 text-primary" />,
    ctaLabel: "Sohbete git",
    ctaHref: "/chat",
  },
  {
    eyebrow: "3. Hedefler ve zarflar",
    title: "Tatil, eğitim, market — her hedef ve zarf burada",
    body: "Birikim hedefi belirli bir tutara ulaşmak için para ayırır; tasarruf hedefi bir gider kategorisini kontrollü azaltır. Zarflar ay başı bütçeyi parçalara böler.",
    icon: <Target className="h-6 w-6 text-primary" />,
    ctaLabel: "Hedeflere git",
    ctaHref: "/goals",
  },
  {
    eyebrow: "4. Dersler",
    title: "Finans Okulu kısa, somut anlatımlarla yanında",
    body: "Faiz, enflasyon, asgari ödeme gibi başlıkları sohbet üzerinden açar; çocuk modunda kumbara ve harçlık örnekleriyle gelir. Bu hafta sorusu da burada.",
    icon: <BookOpen className="h-6 w-6 text-primary" />,
    ctaLabel: "Dersleri aç",
    ctaHref: "/learn",
  },
];

type OnboardingTourProps = {
  /** Skip showing the tour entirely (e.g., when in kid mode). */
  disabled?: boolean;
};

export function OnboardingTour({ disabled = false }: OnboardingTourProps) {
  const [open, setOpen] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (disabled) return;
    try {
      const seen = window.localStorage.getItem(STORAGE_KEY);
      if (!seen) {
        // Delay slightly so the dashboard layout is visible behind the overlay
        // and the modal feels like a guided pop, not a blocking gate.
        const timer = window.setTimeout(() => setOpen(true), 600);
        return () => window.clearTimeout(timer);
      }
    } catch {
      // localStorage unavailable — silently skip the tour to avoid blocking UI.
    }
    return undefined;
  }, [disabled]);

  function markDone(reason: "completed" | "skipped") {
    try {
      window.localStorage.setItem(STORAGE_KEY, reason);
    } catch {
      // best-effort persistence
    }
    setOpen(false);
  }

  if (disabled || !open) return null;

  const step = STEPS[stepIndex] ?? STEPS[0];
  if (step === undefined) return null;
  const isLast = stepIndex === STEPS.length - 1;

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-black/45 p-4 backdrop-blur-sm sm:items-center">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
        className="relative w-full max-w-lg rounded-[1.6rem] border border-border/80 bg-card p-5 shadow-2xl sm:p-7"
      >
        <button
          type="button"
          onClick={() => markDone("skipped")}
          aria-label="Turu kapat"
          className="absolute right-3 top-3 grid h-8 w-8 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-muted/55 hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="flex items-start gap-3">
          <span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-primary/10">
            {step.icon}
          </span>
          <div className="min-w-0">
            <p className="text-[0.65rem] font-bold uppercase tracking-[0.18em] text-muted-foreground">
              {step.eyebrow}
            </p>
            <h2
              id="onboarding-title"
              className="mt-1 font-display text-xl font-black leading-tight sm:text-2xl"
            >
              {step.title}
            </h2>
          </div>
        </div>

        <p className="mt-3 text-sm leading-6 text-muted-foreground sm:text-base">{step.body}</p>

        <div className="mt-5 flex items-center justify-between gap-2">
          <div className="flex items-center gap-1.5" aria-hidden="true">
            {STEPS.map((_, index) => (
              <span
                key={index}
                className={cn(
                  "h-1.5 rounded-full transition-all",
                  index === stepIndex ? "w-6 bg-primary" : "w-1.5 bg-muted-foreground/45",
                )}
              />
            ))}
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {step.ctaHref !== undefined && step.ctaLabel !== undefined ? (
              <Button asChild size="sm" variant="outline" onClick={() => markDone("completed")}>
                <Link href={step.ctaHref}>{step.ctaLabel}</Link>
              </Button>
            ) : null}
            {isLast ? (
              <Button type="button" size="sm" onClick={() => markDone("completed")}>
                Turu bitir
              </Button>
            ) : (
              <Button
                type="button"
                size="sm"
                onClick={() => setStepIndex((current) => Math.min(current + 1, STEPS.length - 1))}
              >
                Sonraki
                <ArrowRight className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>

        {stepIndex === 0 ? (
          <button
            type="button"
            onClick={() => markDone("skipped")}
            className="mt-3 text-xs font-bold text-muted-foreground hover:text-foreground"
          >
            Şimdi atla
          </button>
        ) : null}
      </div>
    </div>
  );
}
