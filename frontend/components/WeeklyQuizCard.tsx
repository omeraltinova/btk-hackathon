"use client";

import { Check, HelpCircle, Sparkles, X } from "lucide-react";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

type WeeklyQuestion = {
  id: string;
  prompt: string;
  options: [string, string, string];
  correctIndex: 0 | 1 | 2;
  explanation: string;
};

// Curated finance literacy questions; rotates weekly. Educational only — no
// product, fund, or buy/sell recommendation (P7, A-4).
const WEEKLY_QUESTIONS: WeeklyQuestion[] = [
  {
    id: "faiz-yon",
    prompt: "Para bankaya yatırıldığında faiz hangi yönde çalışır?",
    options: [
      "Mevduat sahibinin lehine — banka ekstra kazanç öder.",
      "Banka müşteriden ek ücret talep eder.",
      "Hiçbir taraf için fark yaratmaz.",
    ],
    correctIndex: 0,
    explanation:
      "Mevduatta banka, paranı bir süre kullanmak için sana faiz öder. Kredi kullanırken durum tersine döner ve faizi sen ödersin.",
  },
  {
    id: "enflasyon-alim-gucu",
    prompt: "Yüksek enflasyon ortamında 'alım gücü' kavramına ne olur?",
    options: ["Genelde azalır.", "Otomatik olarak artar.", "Etkilenmez."],
    correctIndex: 0,
    explanation:
      "Enflasyon mal ve hizmet fiyatlarını artırdığı için aynı parayla daha az şey alınır; bu da alım gücünün azaldığı anlamına gelir.",
  },
  {
    id: "acil-fon-hedef",
    prompt: "Acil durum fonu için genel olarak önerilen hedef tutar nedir?",
    options: [
      "Aylık zorunlu giderlerin 3–6 katı.",
      "Yıllık gelirin yarısı.",
      "Üç günlük market giderine eşit bir tutar.",
    ],
    correctIndex: 0,
    explanation:
      "Zorunlu giderleri (kira, fatura, market, taksit) 3–6 ay karşılayacak bir tampon yaygın kullanılan eşiktir. Tek gelirli aileler üst banda yakın hedef seçer.",
  },
  {
    id: "asgari-tuzak",
    prompt: "Kredi kartında sadece asgari ödeme yapmanın olası sonucu nedir?",
    options: [
      "Kalan bakiye faizlenmeye devam eder ve borç zamanla büyüyebilir.",
      "Borç anında kapanır.",
      "Faiz oranı otomatik olarak sıfırlanır.",
    ],
    correctIndex: 0,
    explanation:
      "Asgari ödeme sadece gecikmeyi önler; kalan bakiye bileşik faizle birlikte sonraki dönemlere aktarılır ve borç daha uzun sürede kapanır.",
  },
  {
    id: "zarf-mantigi",
    prompt: "Zarf bütçesi yaklaşımında 'zarf' ne işe yarar?",
    options: [
      "Her gider kategorisine ay başından önceden bir üst limit ayırır.",
      "Banka dekontlarını saklamak için kullanılır.",
      "Yatırım enstrümanlarının sınıflandırılmasıdır.",
    ],
    correctIndex: 0,
    explanation:
      "Market, fatura, ulaşım gibi her kategoriye ay başından önceden limit konur; ay içinde harcama bu zarflar içinde tutulmaya çalışılır.",
  },
  {
    id: "bilesik-faiz",
    prompt: "Bileşik faizde 'faizin faizi' ne anlama gelir?",
    options: [
      "Önceki dönemin faizi yeni anaparaya eklenir ve sonraki faiz onun üzerinden hesaplanır.",
      "Bankaya iki kat komisyon ödenir.",
      "Faiz oranı her yıl yarıya iner.",
    ],
    correctIndex: 0,
    explanation:
      "Anapara × (1 + faiz oranı) ^ dönem sayısı formülü, her dönem kazanılan faizin bir sonraki dönem anaparaya katılması anlamına gelir.",
  },
  {
    id: "abonelik-yillik",
    prompt: "Aylık 230 ₺ olan bir aboneliğin yıllık etkisi yaklaşık ne kadardır?",
    options: ["Yaklaşık 2.760 ₺.", "Yaklaşık 460 ₺.", "Yaklaşık 11.500 ₺."],
    correctIndex: 0,
    explanation:
      "230 ₺ × 12 ay ≈ 2.760 ₺. Küçük tutarların yıllığa çevrilmesi gerçek bütçe etkisini netleştirir.",
  },
  {
    id: "ihtiyac-istek",
    prompt: "Karar verirken 'ihtiyaç' ve 'istek' farkı neden önemlidir?",
    options: [
      "Önce ihtiyaçlar karşılanır; istekler bütçe ve hedefe göre ertelenebilir.",
      "İhtiyaçlar istekten daima daha pahalıdır.",
      "Aralarında pratik bir fark yoktur.",
    ],
    correctIndex: 0,
    explanation:
      "İhtiyaçlar (kira, market, fatura) önceliklendirilir. İstekler (eğlence, yükseltme) bütçe ve birikim hedefiyle dengelenerek planlanır.",
  },
  {
    id: "tasarruf-onsira",
    prompt:
      "Tasarrufu sürdürülebilir kılmak için yaygın olarak önerilen 'önce ayır, sonra harca' yaklaşımının özü nedir?",
    options: [
      "Maaş gelir gelmez belirli bir oranı otomatik olarak ayrı bir hesaba aktarmak.",
      "Ay sonunda kalan tutarı biriktirmek.",
      "Birikimi tamamen ihtimale bırakmak.",
    ],
    correctIndex: 0,
    explanation:
      "Otomatik talimat ile maaş günü tasarruf hesabına aktarım yapmak; harcama eğiliminin geliri tamamen tüketmesini engeller.",
  },
  {
    id: "ekstre-son-odeme",
    prompt: "Kredi kartı ekstresinde 'son ödeme tarihi' neyi gösterir?",
    options: [
      "Faiz veya gecikme cezası doğmadan ödeme yapılması gereken son günü.",
      "Kartın ilk kullanıldığı tarihi.",
      "Banka şubesinin kapanış tarihini.",
    ],
    correctIndex: 0,
    explanation:
      "Son ödeme tarihinden önce yapılan ödeme gecikme cezası veya faiz oluşturmaz. Bu tarih genelde ekstre tarihinden 10 gün sonra olur.",
  },
];

function getIsoWeekId(date: Date): string {
  // ISO week year + week number → stable string id used as both rotation seed
  // and localStorage key.
  const target = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNumber = (target.getUTCDay() + 6) % 7;
  target.setUTCDate(target.getUTCDate() - dayNumber + 3);
  const firstThursday = new Date(Date.UTC(target.getUTCFullYear(), 0, 4));
  const weekNumber =
    1 +
    Math.round(
      ((target.getTime() - firstThursday.getTime()) / 86400000 -
        3 +
        ((firstThursday.getUTCDay() + 6) % 7)) /
        7,
    );
  return `${target.getUTCFullYear()}-W${String(weekNumber).padStart(2, "0")}`;
}

function weekIndexFromId(weekId: string): number {
  const match = weekId.match(/W(\d{1,2})/);
  if (!match) return 0;
  return Number(match[1]);
}

const STORAGE_KEY = "cuzdan-kocu.weekly-quiz";

type StoredAnswer = {
  weekId: string;
  answeredIndex: number | null;
  correct: boolean;
};

function readStored(): StoredAnswer | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (
      typeof parsed === "object" &&
      parsed !== null &&
      "weekId" in parsed &&
      typeof (parsed as StoredAnswer).weekId === "string"
    ) {
      return parsed as StoredAnswer;
    }
  } catch {
    // ignore malformed stored data
  }
  return null;
}

function writeStored(value: StoredAnswer): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // best-effort persistence
  }
}

export function WeeklyQuizCard() {
  const [weekId, setWeekId] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  useEffect(() => {
    const id = getIsoWeekId(new Date());
    setWeekId(id);
    const stored = readStored();
    if (stored !== null && stored.weekId === id) {
      setSelectedIndex(stored.answeredIndex);
    }
  }, []);

  if (weekId === null) return null;
  const currentWeekId: string = weekId;

  const question =
    WEEKLY_QUESTIONS[weekIndexFromId(currentWeekId) % WEEKLY_QUESTIONS.length] ??
    WEEKLY_QUESTIONS[0];
  if (question === undefined) return null;
  const currentQuestion: WeeklyQuestion = question;
  const isAnswered = selectedIndex !== null;
  const isCorrect = selectedIndex === currentQuestion.correctIndex;

  function handleSelect(index: number) {
    if (isAnswered) return;
    setSelectedIndex(index);
    writeStored({
      weekId: currentWeekId,
      answeredIndex: index,
      correct: index === currentQuestion.correctIndex,
    });
  }

  return (
    <section className="receipt-tape relative overflow-hidden p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <span className="stamp-label bg-background/70 text-primary">
          <Sparkles className="h-3.5 w-3.5" />
          Bu hafta sorusu
        </span>
        <span className="text-xs font-bold text-muted-foreground">{currentWeekId}</span>
      </div>
      <h2 className="mt-3 flex items-start gap-2 font-display text-xl font-black leading-snug sm:text-2xl">
        <HelpCircle className="mt-1 h-5 w-5 shrink-0 text-primary" />
        <span>{currentQuestion.prompt}</span>
      </h2>
      <ul className="mt-4 space-y-2">
        {currentQuestion.options.map((option, index) => {
          const isThisSelected = selectedIndex === index;
          const isThisCorrect = index === currentQuestion.correctIndex;
          const shouldHighlightCorrect = isAnswered && isThisCorrect;
          const shouldHighlightWrong = isAnswered && isThisSelected && !isThisCorrect;
          return (
            <li key={index}>
              <button
                type="button"
                disabled={isAnswered}
                onClick={() => handleSelect(index)}
                aria-pressed={isThisSelected}
                className={cn(
                  "flex w-full items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-left text-sm font-semibold transition-colors",
                  !isAnswered &&
                    "border-border/70 bg-background/70 hover:border-primary/40 hover:bg-primary/5",
                  shouldHighlightCorrect && "border-primary bg-primary/15 text-foreground",
                  shouldHighlightWrong && "border-destructive bg-destructive/10 text-foreground",
                  isAnswered &&
                    !shouldHighlightCorrect &&
                    !shouldHighlightWrong &&
                    "border-border/60 bg-background/55 text-muted-foreground",
                )}
              >
                <span>{option}</span>
                {shouldHighlightCorrect ? (
                  <Check className="h-4 w-4 shrink-0 text-primary" />
                ) : null}
                {shouldHighlightWrong ? <X className="h-4 w-4 shrink-0 text-destructive" /> : null}
              </button>
            </li>
          );
        })}
      </ul>
      {isAnswered ? (
        <div
          className={cn(
            "mt-4 rounded-2xl border p-3 text-sm leading-6",
            isCorrect
              ? "border-primary/40 bg-primary/10 text-foreground"
              : "border-destructive/35 bg-destructive/10 text-foreground",
          )}
        >
          <p className="font-bold">{isCorrect ? "Doğru cevap." : "Bir sonraki haftaya not."}</p>
          <p className="mt-1 text-muted-foreground">{currentQuestion.explanation}</p>
          <p className="mt-2 text-xs text-muted-foreground">
            Sonraki soru pazartesi yenilenir; bu hafta için yanıt kaydedildi.
          </p>
        </div>
      ) : (
        <p className="mt-4 text-xs text-muted-foreground">
          Bir şıkka dokun; cevap haftalık olarak yenilenir.
        </p>
      )}
    </section>
  );
}
