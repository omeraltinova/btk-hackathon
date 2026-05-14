"use client";

import { BookOpen, ImagePlus, Loader2, Volume2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { streamChat } from "@/lib/sse";
import type { ChatStreamEvent } from "@/lib/types";

type Lesson = {
  title: string;
  prompt: string;
  tag: string;
  sensitive?: boolean;
};

const LESSONS: Lesson[] = [
  {
    title: "Faiz nedir?",
    prompt: "Faiz nedir? Günlük hayattan basit örneklerle açıkla.",
    tag: "Temel kavram",
  },
  {
    title: "Enflasyon nedir?",
    prompt: "Enflasyon nedir? Aile bütçesi üzerinden anlat.",
    tag: "Günlük hayat",
  },
  {
    title: "Bütçe nedir?",
    prompt: "Bütçe nedir? Zarf bütçesi örneğiyle anlat.",
    tag: "Planlama",
  },
  {
    title: "Tasarruf nedir?",
    prompt: "Tasarruf nedir? Küçük alışkanlıklarla nasıl başlanır anlat.",
    tag: "Hedefler",
  },
  {
    title: "Kredi kartı asgari ödeme nedir?",
    prompt: "Kredi kartı asgari ödeme nedir? Risklerini basitçe anlat.",
    tag: "Borç yönetimi",
  },
  {
    title: "Para piyasası fonu nedir?",
    prompt:
      "Para piyasası fonu nedir? Sadece eğitim amaçlı anlat; belirli fon önerme, al/sat/tut tavsiyesi verme.",
    tag: "Yatırım kavramı",
    sensitive: true,
  },
];

const DEFAULT_LESSON = LESSONS[0] as Lesson;

function lessonPrompt(lesson: Lesson, visual: boolean): string {
  const suffix = visual ? " Görsel olarak da anlat." : "";
  return `${lesson.prompt} Yatırım tavsiyesi verme; sadece eğitim amaçlı açıkla.${suffix}`;
}

export function FinancialLessonsClient() {
  const [selectedLesson, setSelectedLesson] = useState<Lesson>(DEFAULT_LESSON);
  const [answer, setAnswer] = useState("");
  const [image, setImage] = useState<{ url: string; alt: string } | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function runLesson(lesson: Lesson, visual = false) {
    setSelectedLesson(lesson);
    setAnswer("");
    setImage(null);
    setError(null);
    setIsLoading(true);
    try {
      await streamChat({ message: lessonPrompt(lesson, visual) }, (event: ChatStreamEvent) => {
        if (event.type === "delta") {
          setAnswer((current) => `${current}${event.content}`);
        }
        if (event.type === "image") {
          setImage({ url: event.image_url, alt: event.alt_text });
        }
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ders hazırlanamadı, tekrar dener misin?");
    } finally {
      setIsLoading(false);
    }
  }

  function speakAnswer() {
    if (!answer || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(answer);
    utterance.lang = "tr-TR";
    window.speechSynthesis.speak(utterance);
  }

  return (
    <main className="space-y-6 p-4 sm:p-6 lg:p-8">
      <section className="receipt-tape hard-shadow rounded-[2rem] border border-border/80 bg-card p-5 sm:p-7">
        <div className="max-w-3xl space-y-3">
          <span className="stamp-label bg-primary/10 text-primary">Finans Okulu</span>
          <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
            Hazır ders seç, koç anlatsın
          </h1>
          <p className="text-sm leading-6 text-muted-foreground sm:text-base">
            Dersler kontrollü başlıklardan başlar; AI sadece eğitim amaçlı açıklar. Fon, hisse,
            kripto, altın veya döviz başlıklarında belirli ürün önerisi ve al/sat/tut tavsiyesi
            verilmez.
          </p>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="grid gap-3">
          {LESSONS.map((lesson) => (
            <article
              key={lesson.title}
              className="ledger-card rounded-[1.4rem] border border-border/80 bg-card p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                    {lesson.tag}
                  </p>
                  <h2 className="mt-1 font-display text-xl font-bold">{lesson.title}</h2>
                  {lesson.sensitive ? (
                    <p className="mt-2 text-xs text-muted-foreground">
                      Eğitim amaçlıdır; ürün veya getiri önerisi içermez.
                    </p>
                  ) : null}
                </div>
                <BookOpen className="h-5 w-5 text-primary" />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button size="sm" disabled={isLoading} onClick={() => void runLesson(lesson)}>
                  Anlat
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={isLoading}
                  onClick={() => void runLesson(lesson, true)}
                >
                  <ImagePlus className="h-4 w-4" />
                  Görselle anlat
                </Button>
              </div>
            </article>
          ))}
        </div>

        <article className="ledger-card min-h-[28rem] rounded-[1.8rem] border border-border/80 bg-card p-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                Seçili ders
              </p>
              <h2 className="mt-1 font-display text-2xl font-bold">{selectedLesson.title}</h2>
            </div>
            <Button size="sm" variant="ghost" disabled={!answer} onClick={speakAnswer}>
              <Volume2 className="h-4 w-4" />
              Sesli oku
            </Button>
          </div>

          <div className="mt-5 rounded-[1.4rem] border border-dashed border-border/80 bg-muted/35 p-4 text-sm leading-7 text-foreground/85">
            {isLoading && !answer ? (
              <p className="flex items-center gap-2 text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Koç dersi hazırlıyor...
              </p>
            ) : null}
            {answer ? <p className="whitespace-pre-wrap">{answer}</p> : null}
            {!isLoading && !answer && !error ? (
              <p className="text-muted-foreground">
                Soldan bir ders seç. İstersen önce metin olarak oku, istersen görsel anlatım da
                iste.
              </p>
            ) : null}
            {error ? <p className="text-destructive">{error}</p> : null}
          </div>

          {image ? (
            <figure className="mt-5 overflow-hidden rounded-[1.5rem] border border-border/80 bg-background">
              {/* eslint-disable-next-line @next/next/no-img-element -- Runtime MinIO URL comes from existing illustration tool. */}
              <img src={image.url} alt={image.alt} className="w-full object-cover" />
              <figcaption className="px-4 py-3 text-xs text-muted-foreground">
                {image.alt}
              </figcaption>
            </figure>
          ) : null}
        </article>
      </section>
    </main>
  );
}
