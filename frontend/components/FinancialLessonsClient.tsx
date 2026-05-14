"use client";

import { BookOpen, CheckCircle2, ImagePlus, MessageSquareText } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { rememberActiveConversationId, rememberPendingChatMessage } from "@/lib/chat-session";
import { cn } from "@/lib/utils";

type LessonLevel = "child" | "beginner" | "intermediate" | "advanced";

type Lesson = {
  id: string;
  title: string;
  prompt: string;
  tag: string;
  level: LessonLevel;
  sensitive?: boolean;
};

const LEVEL_LABELS: Record<LessonLevel, string> = {
  child: "Çocuk",
  beginner: "Başlangıç",
  intermediate: "Orta",
  advanced: "İleri",
};

const LESSONS: Lesson[] = [
  {
    id: "kumbara",
    title: "Kumbara nasıl büyür?",
    prompt: "Kumbara nasıl büyür? Harçlık ve küçük hedef örnekleriyle çocuk dilinde anlat.",
    tag: "Harçlık",
    level: "child",
  },
  {
    id: "faiz",
    title: "Faiz nedir?",
    prompt: "Faiz nedir? Günlük hayattan basit örneklerle açıkla.",
    tag: "Temel kavram",
    level: "beginner",
  },
  {
    id: "enflasyon",
    title: "Enflasyon nedir?",
    prompt: "Enflasyon nedir? Aile bütçesi üzerinden anlat.",
    tag: "Günlük hayat",
    level: "beginner",
  },
  {
    id: "butce",
    title: "Bütçe nedir?",
    prompt: "Bütçe nedir? Zarf bütçesi örneğiyle anlat.",
    tag: "Planlama",
    level: "beginner",
  },
  {
    id: "tasarruf",
    title: "Tasarruf nedir?",
    prompt: "Tasarruf nedir? Küçük alışkanlıklarla nasıl başlanır anlat.",
    tag: "Hedefler",
    level: "beginner",
  },
  {
    id: "asgari-odeme",
    title: "Kredi kartı asgari ödeme nedir?",
    prompt: "Kredi kartı asgari ödeme nedir? Risklerini basitçe anlat.",
    tag: "Borç yönetimi",
    level: "intermediate",
  },
  {
    id: "nakit-akisi",
    title: "Nakit akışı nasıl okunur?",
    prompt: "Nakit akışı nasıl okunur? Gelir, gider ve tekrarlayan ödemelerle açıkla.",
    tag: "Analiz",
    level: "intermediate",
  },
  {
    id: "para-piyasasi-fonu",
    title: "Para piyasası fonu nedir?",
    prompt:
      "Para piyasası fonu nedir? Eğitim amaçlı, günlük hayattan örneklerle genel işleyişini ve risklerini anlat; belirli ürün adı veya getiri iddiası kullanma.",
    tag: "Yatırım kavramı",
    level: "advanced",
    sensitive: true,
  },
  {
    id: "risk-vade",
    title: "Risk ve vade ilişkisi nedir?",
    prompt:
      "Risk ve vade ilişkisi nedir? Eğitim amaçlı genel kavramları anlat; belirli ürün veya al-sat önerisi verme.",
    tag: "Risk okuryazarlığı",
    level: "advanced",
    sensitive: true,
  },
];

const PROGRESS_KEY = "cuzdan-kocu.learn.progress";
const DEFAULT_LESSON = LESSONS[0] as Lesson;

function lessonPrompt(lesson: Lesson, visual: boolean): string {
  const suffix = visual ? " Görsel olarak da anlat." : "";
  return `${lesson.prompt} Bu bir ders anlatımıdır; ürün seçimi veya getiri iddiası yapma.${suffix}`;
}

function readProgress(): string[] {
  try {
    const raw = window.localStorage.getItem(PROGRESS_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === "string")
      : [];
  } catch {
    return [];
  }
}

function writeProgress(ids: string[]): void {
  try {
    window.localStorage.setItem(PROGRESS_KEY, JSON.stringify(ids));
  } catch {
    // Local progress is a convenience only; lessons still work without storage.
  }
}

export function FinancialLessonsClient() {
  const router = useRouter();
  const [activeLevel, setActiveLevel] = useState<LessonLevel>("beginner");
  const [selectedLesson, setSelectedLesson] = useState<Lesson>(DEFAULT_LESSON);
  const [completedIds, setCompletedIds] = useState<string[]>([]);
  const [routingAction, setRoutingAction] = useState<string | null>(null);

  useEffect(() => {
    setCompletedIds(readProgress());
  }, []);

  const activeLessons = LESSONS.filter((lesson) => lesson.level === activeLevel);
  const completedCount = LESSONS.filter((lesson) => completedIds.includes(lesson.id)).length;
  const progressPercent = Math.round((completedCount / LESSONS.length) * 100);
  const nextLesson = useMemo(
    () => LESSONS.find((lesson) => !completedIds.includes(lesson.id)) ?? DEFAULT_LESSON,
    [completedIds],
  );

  function markStarted(lesson: Lesson) {
    setCompletedIds((current) => {
      const next = Array.from(new Set([...current, lesson.id]));
      writeProgress(next);
      return next;
    });
  }

  function startLessonInChat(lesson: Lesson, visual = false) {
    const actionKey = `${lesson.title}-${visual ? "visual" : "text"}`;
    setSelectedLesson(lesson);
    setRoutingAction(actionKey);
    markStarted(lesson);
    rememberPendingChatMessage({
      message: lessonPrompt(lesson, visual),
      source: "learn",
      title: lesson.title,
      startNew: true,
    });
    rememberActiveConversationId(null);
    router.push("/chat");
  }

  return (
    <main className="space-y-6 p-4 sm:p-6 lg:p-8">
      <section className="receipt-tape hard-shadow rounded-[2rem] border border-border/80 bg-card p-5 sm:p-7">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-end">
          <div className="max-w-3xl space-y-3">
            <span className="stamp-label bg-primary/10 text-primary">Finans Okulu</span>
            <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
              Seviyene göre ders seç, sohbette başlat
            </h1>
            <p className="text-sm leading-6 text-muted-foreground sm:text-base">
              Dersler kontrollü başlıklardan başlar; koç cevabı sohbet ekranında üretir. Fon, hisse,
              kripto, altın veya döviz başlıklarında belirli ürün seçimi ve getiri iddiası yoktur.
            </p>
          </div>
          <div className="rounded-[1.5rem] border border-dashed border-primary/30 bg-primary/5 p-4">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
              Ders ilerlemesi
            </p>
            <p className="mt-2 font-display text-3xl font-black">%{progressPercent}</p>
            <div className="mt-3 h-3 overflow-hidden rounded-full bg-background/80">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              Sıradaki ders: <strong className="text-foreground">{nextLesson.title}</strong>
            </p>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap gap-2">
        {(Object.keys(LEVEL_LABELS) as LessonLevel[]).map((level) => (
          <Button
            key={level}
            type="button"
            variant={activeLevel === level ? "default" : "outline"}
            onClick={() => setActiveLevel(level)}
          >
            {LEVEL_LABELS[level]}
          </Button>
        ))}
      </div>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {activeLessons.map((lesson) => {
            const completed = completedIds.includes(lesson.id);
            return (
              <article
                key={lesson.id}
                className={cn(
                  "ledger-card flex min-h-[12rem] flex-col rounded-[1.4rem] border border-border/80 bg-card p-4",
                  completed ? "border-primary/40 bg-primary/5" : "",
                )}
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
                  {completed ? (
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                  ) : (
                    <BookOpen className="h-5 w-5 text-primary" />
                  )}
                </div>
                <div className="mt-auto flex flex-wrap gap-2 pt-4">
                  <Button
                    size="sm"
                    disabled={routingAction !== null}
                    onClick={() => startLessonInChat(lesson)}
                  >
                    <MessageSquareText className="h-4 w-4" />
                    Sohbette anlat
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={routingAction !== null}
                    onClick={() => startLessonInChat(lesson, true)}
                  >
                    <ImagePlus className="h-4 w-4" />
                    Görselle anlat
                  </Button>
                </div>
              </article>
            );
          })}
        </div>

        <aside className="ledger-card h-fit rounded-[1.8rem] border border-border/80 bg-card p-5">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
            Seçili ders
          </p>
          <h2 className="mt-2 font-display text-2xl font-bold">{selectedLesson.title}</h2>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Ders yanıtı sohbet masasında açılır; araç izi, görsel ve sesli okuma aynı akışta kalır.
          </p>
          <div className="mt-5 flex flex-col gap-2">
            <Button
              disabled={routingAction !== null}
              onClick={() => startLessonInChat(selectedLesson)}
            >
              <MessageSquareText className="h-4 w-4" />
              Sohbette anlat
            </Button>
            <Button
              variant="secondary"
              disabled={routingAction !== null}
              onClick={() => startLessonInChat(selectedLesson, true)}
            >
              <ImagePlus className="h-4 w-4" />
              Görselle anlat
            </Button>
          </div>
        </aside>
      </section>
    </main>
  );
}
