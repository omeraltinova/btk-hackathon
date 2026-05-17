"use client";

import { BookOpen, CheckCircle2, ImagePlus, MessageSquareText, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { WeeklyQuizCard } from "@/components/WeeklyQuizCard";
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
    id: "ihtiyac-istek",
    title: "İhtiyaç mı, istek mi?",
    prompt:
      "İhtiyaç ile istek arasındaki fark nedir? Atıştırmalık, oyuncak ve okul eşyası örnekleriyle çocuk dilinde anlat.",
    tag: "Karar verme",
    level: "child",
  },
  {
    id: "harclik-plani",
    title: "Harçlık nasıl bölünür?",
    prompt:
      "Harçlık nasıl bölünür? Harcama, birikim ve paylaşma kavanozları örneğiyle çocuk dilinde anlat.",
    tag: "Planlama",
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
    id: "gelir-gider",
    title: "Gelir ve gider farkı nedir?",
    prompt: "Gelir ve gider farkı nedir? Aylık aile bütçesi üzerinden basitçe anlat.",
    tag: "Temel bütçe",
    level: "beginner",
  },
  {
    id: "acil-durum-fonu",
    title: "Acil durum fonu nedir?",
    prompt:
      "Acil durum fonu nedir? Beklenmedik tamir ve sağlık gideri örnekleriyle neden gerekli olduğunu anlat.",
    tag: "Güvence",
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
    id: "abonelik-takibi",
    title: "Abonelikleri neden takip etmeliyiz?",
    prompt:
      "Abonelikleri neden takip etmeliyiz? Tekrarlayan küçük ödemelerin bütçeye etkisini örneklerle anlat.",
    tag: "Alışkanlıklar",
    level: "intermediate",
  },
  {
    id: "ekstre-okuma",
    title: "Kredi kartı ekstresi nasıl okunur?",
    prompt:
      "Kredi kartı ekstresi nasıl okunur? Dönem borcu, asgari ödeme, son ödeme tarihi ve faiz bölümlerini sade biçimde açıkla.",
    tag: "Borç okuryazarlığı",
    level: "intermediate",
  },
  {
    id: "bilesik-faiz",
    title: "Bileşik faiz nedir?",
    prompt:
      "Bileşik faiz nedir? Eğitim amaçlı, zaman içindeki büyümeyi basit sayısal örnekle anlat; belirli ürün adı veya getiri iddiası kullanma.",
    tag: "Zaman etkisi",
    level: "advanced",
    sensitive: true,
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
  {
    id: "cesitlendirme",
    title: "Çeşitlendirme nedir?",
    prompt:
      "Çeşitlendirme nedir? Eğitim amaçlı genel mantığını anlat; belirli ürün, oran veya al-sat önerisi verme.",
    tag: "Risk yönetimi",
    level: "advanced",
    sensitive: true,
  },
];

const PROGRESS_KEY = "cuzdan-kocu.learn.progress";
const selectClassName =
  "flex h-11 w-full rounded-2xl border border-input bg-background/80 px-4 py-2 text-sm ring-offset-background transition-all duration-200 ease-quint focus-visible:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

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
  const [startedIds, setStartedIds] = useState<string[]>([]);
  const [routingAction, setRoutingAction] = useState<string | null>(null);
  const [customTopic, setCustomTopic] = useState("");
  const [customLevel, setCustomLevel] = useState<LessonLevel>("beginner");
  const [customDuration, setCustomDuration] = useState("5");
  const [customExamples, setCustomExamples] = useState(true);
  const [customQuiz, setCustomQuiz] = useState(true);
  const [customVisual, setCustomVisual] = useState(false);

  useEffect(() => {
    setStartedIds(readProgress());
  }, []);

  const activeLessons = LESSONS.filter((lesson) => lesson.level === activeLevel);
  const startedCount = LESSONS.filter((lesson) => startedIds.includes(lesson.id)).length;
  const progressPercent = Math.round((startedCount / LESSONS.length) * 100);
  const nextLesson = useMemo(
    () => LESSONS.find((lesson) => !startedIds.includes(lesson.id)),
    [startedIds],
  );

  function markStarted(lesson: Lesson) {
    setStartedIds((current) => {
      const next = Array.from(new Set([...current, lesson.id]));
      writeProgress(next);
      return next;
    });
  }

  function startLessonInChat(lesson: Lesson, visual = false) {
    const actionKey = `${lesson.title}-${visual ? "visual" : "text"}`;
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

  function startCustomLesson(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const topic = customTopic.trim();
    if (!topic) return;
    const duration = Math.max(3, Math.min(Number(customDuration) || 5, 12));
    setRoutingAction("custom-lesson");
    rememberPendingChatMessage({
      message: [
        "Özel ders oluştur",
        `Konu: ${topic}`,
        `Seviye: ${customLevel}`,
        `Süre: ${duration}`,
        `Örnekler: ${customExamples ? "evet" : "hayır"}`,
        `Mini quiz: ${customQuiz ? "evet" : "hayır"}`,
        `Görsel: ${customVisual ? "evet" : "hayır"}`,
      ].join(" | "),
      source: "learn",
      title: `${topic}: özel ders`,
      startNew: true,
    });
    rememberActiveConversationId(null);
    router.push("/chat");
  }

  return (
    <main className="space-y-6 p-4 sm:p-6 lg:p-8">
      <WeeklyQuizCard />
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
              Başlanan dersler
            </p>
            <p className="mt-2 font-display text-3xl font-black">%{progressPercent}</p>
            <div className="mt-3 h-3 overflow-hidden rounded-full bg-background/80">
              <div
                className="h-full rounded-full bg-primary"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <p className="mt-3 text-sm text-muted-foreground">
              {startedCount}/{LESSONS.length} ders başlatıldı.
            </p>
            <p className="mt-1 text-sm text-muted-foreground">
              {nextLesson ? (
                <>
                  Sıradaki ders: <strong className="text-foreground">{nextLesson.title}</strong>
                </>
              ) : (
                "Tüm dersler başlatıldı."
              )}
            </p>
          </div>
        </div>
      </section>

      <section className="grid gap-5 lg:grid-cols-[0.86fr_1.14fr] lg:items-stretch">
        <div className="ledger-sheet p-5 sm:p-7">
          <div className="relative z-10 space-y-3">
            <span className="stamp-label bg-background/70 text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              Özel ders
            </span>
            <h2 className="font-display text-3xl font-black tracking-[-0.04em]">
              Kendi konunu koça ver
            </h2>
            <p className="text-sm leading-6 text-muted-foreground">
              Ders kalıcı kaydedilmez; sohbet içinde anlık bir ders planı, örnekler ve mini quiz
              üretir. Ürün seçimi ve getiri iddiası yine kapalıdır.
            </p>
          </div>
        </div>

        <form className="receipt-tape space-y-4 p-5 sm:p-6" onSubmit={startCustomLesson}>
          <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
            <div className="space-y-2">
              <label htmlFor="custom-lesson-topic" className="text-sm font-medium">
                Konu
              </label>
              <Input
                id="custom-lesson-topic"
                value={customTopic}
                onChange={(event) => setCustomTopic(event.target.value)}
                placeholder="Örn. abonelik bütçesi, acil durum fonu, ihtiyaç-istek"
                maxLength={90}
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="custom-lesson-duration" className="text-sm font-medium">
                Süre
              </label>
              <Input
                id="custom-lesson-duration"
                type="number"
                min={3}
                max={12}
                value={customDuration}
                onChange={(event) => setCustomDuration(event.target.value)}
                required
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-[12rem_1fr]">
            <div className="space-y-2">
              <label htmlFor="custom-lesson-level" className="text-sm font-medium">
                Seviye
              </label>
              <select
                id="custom-lesson-level"
                className={selectClassName}
                value={customLevel}
                onChange={(event) => setCustomLevel(event.target.value as LessonLevel)}
              >
                {(Object.keys(LEVEL_LABELS) as LessonLevel[]).map((level) => (
                  <option key={level} value={level}>
                    {LEVEL_LABELS[level]}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid gap-2 sm:grid-cols-3 sm:pt-7">
              {(
                [
                  [customExamples, setCustomExamples, "Örnekli"],
                  [customQuiz, setCustomQuiz, "Mini quiz"],
                  [customVisual, setCustomVisual, "Görsel"],
                ] as const
              ).map(([checked, setter, label]) => (
                <button
                  key={label}
                  type="button"
                  className={cn(
                    "rounded-2xl border px-3 py-2 text-sm font-bold transition-colors",
                    checked
                      ? "bg-primary/12 border-primary/45 text-foreground"
                      : "border-border bg-background/70 text-muted-foreground",
                  )}
                  onClick={() => setter(!checked)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <Button
            type="submit"
            className="w-full"
            disabled={routingAction !== null || !customTopic.trim()}
          >
            <MessageSquareText className="h-4 w-4" />
            Sohbette özel ders oluştur
          </Button>
        </form>
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

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {activeLessons.map((lesson) => {
          const started = startedIds.includes(lesson.id);
          return (
            <article
              key={lesson.id}
              className={cn(
                "ledger-card flex min-h-[12rem] flex-col rounded-[1.4rem] border border-border/80 bg-card p-4",
                started ? "border-primary/40 bg-primary/5" : "",
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
                {started ? (
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
      </section>
    </main>
  );
}
