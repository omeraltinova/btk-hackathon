"use client";

import { BookOpen, ImagePlus, MessageSquareText } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { rememberActiveConversationId, rememberPendingChatMessage } from "@/lib/chat-session";

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
      "Para piyasası fonu nedir? Eğitim amaçlı, günlük hayattan örneklerle genel işleyişini ve risklerini anlat; belirli ürün adı veya getiri iddiası kullanma.",
    tag: "Yatırım kavramı",
    sensitive: true,
  },
];

const DEFAULT_LESSON = LESSONS[0] as Lesson;

function lessonPrompt(lesson: Lesson, visual: boolean): string {
  const suffix = visual ? " Görsel olarak da anlat." : "";
  return `${lesson.prompt} Bu bir ders anlatımıdır; ürün seçimi veya getiri iddiası yapma.${suffix}`;
}

export function FinancialLessonsClient() {
  const router = useRouter();
  const [selectedLesson, setSelectedLesson] = useState<Lesson>(DEFAULT_LESSON);
  const [routingAction, setRoutingAction] = useState<string | null>(null);

  function startLessonInChat(lesson: Lesson, visual = false) {
    const actionKey = `${lesson.title}-${visual ? "visual" : "text"}`;
    setSelectedLesson(lesson);
    setRoutingAction(actionKey);
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
        <div className="max-w-3xl space-y-3">
          <span className="stamp-label bg-primary/10 text-primary">Finans Okulu</span>
          <h1 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
            Hazır ders seç, sohbette başlat
          </h1>
          <p className="text-sm leading-6 text-muted-foreground sm:text-base">
            Dersler kontrollü başlıklardan başlar; koç cevabı sohbet ekranında üretir. Fon, hisse,
            kripto, altın veya döviz başlıklarında belirli ürün seçimi ve getiri iddiası yoktur.
          </p>
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {LESSONS.map((lesson) => (
            <article
              key={lesson.title}
              className="ledger-card flex min-h-[12rem] flex-col rounded-[1.4rem] border border-border/80 bg-card p-4"
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
          ))}
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
