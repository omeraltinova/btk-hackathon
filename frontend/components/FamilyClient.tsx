"use client";

import {
  Baby,
  BarChart3,
  ChartPie,
  Edit3,
  Loader2,
  ShieldCheck,
  Trophy,
  UserPlus,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from "recharts";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { amountToKurus, formatDateTR, formatKurus } from "@/lib/format";
import {
  clearActiveProfile,
  readActiveProfile,
  setActiveProfile,
  type ActiveProfile,
} from "@/lib/active-profile";
import type {
  AgeStatus,
  ChildCreateInput,
  FamilyMember,
  FamilyMemberFinance,
  FamilyOverview,
  FinanceLevel,
  TokenResponse,
} from "@/lib/types";

const selectClassName =
  "flex h-11 w-full rounded-2xl border border-input bg-background/80 px-4 py-2 text-sm ring-offset-background transition-all duration-200 ease-quint focus-visible:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

type FamilyMetricCard = {
  label: string;
  value: string;
  detail: string;
};

type ChildDraft = {
  birthDate: string;
  financeLevel: FinanceLevel;
};

type FamilyHighlight = {
  label: string;
  name: string;
  detail: string;
};

type FamilyChartPoint = {
  name: string;
  role: "parent" | "child";
  income: number;
  expense: number;
  balance: number;
  incomeFormatted: string;
  expenseFormatted: string;
  balanceFormatted: string;
};

type FamilyPiePoint = {
  name: string;
  value: number;
  valueFormatted: string;
};

const CHART_COLORS = [
  "oklch(var(--primary))",
  "oklch(var(--accent))",
  "oklch(0.64 0.1 192)",
  "oklch(0.68 0.12 25)",
  "oklch(0.62 0.11 310)",
  "oklch(0.58 0.13 52)",
];

function chartColor(index: number): string {
  return CHART_COLORS[index % CHART_COLORS.length] ?? "oklch(var(--primary))";
}

const ageStatusLabels: Record<AgeStatus, string> = {
  minor: "18 yaş altı",
  adult: "Yetişkin",
};

const financeLevelLabels: Record<FinanceLevel, string> = {
  child: "Çocuk koç dili",
  beginner: "Başlangıç",
  intermediate: "Orta",
  advanced: "İleri",
};

function calculateClientAge(birthDate: string): number | null {
  if (!birthDate) return null;
  const parsed = new Date(`${birthDate}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - parsed.getFullYear();
  const hadBirthday =
    today.getMonth() > parsed.getMonth() ||
    (today.getMonth() === parsed.getMonth() && today.getDate() >= parsed.getDate());
  if (!hadBirthday) age -= 1;
  return Math.max(age, 0);
}

function suggestedFinanceLevel(birthDate: string): FinanceLevel {
  const age = calculateClientAge(birthDate);
  return age !== null && age < 18 ? "child" : "beginner";
}

function memberAgeText(member: Pick<FamilyMember, "age" | "age_status">): string {
  if (member.age === null) return "Doğum tarihi yok";
  const status = member.age_status ? ageStatusLabels[member.age_status] : "Statü hesaplanıyor";
  return `${member.age} yaş / ${status}`;
}

function formatExpenseShare(value: string): string {
  const numeric = Number(value.replace(",", "."));
  if (!Number.isFinite(numeric)) return "%0";
  return `%${new Intl.NumberFormat("tr-TR", {
    maximumFractionDigits: 1,
    minimumFractionDigits: 0,
  }).format(numeric)}`;
}

function latestTransactionAmount(member: FamilyMemberFinance): string {
  if (!member.latest_transaction_amount || !member.latest_transaction_type) return "";
  const sign = member.latest_transaction_type === "expense" ? -1 : 1;
  return formatKurus(amountToKurus(member.latest_transaction_amount) * sign);
}

function latestTransactionText(member: FamilyMemberFinance): string {
  if (!member.latest_transaction_at) return "Bu ay hareket yok";
  const merchant = member.latest_transaction_merchant ?? "Son işlem";
  const amount = latestTransactionAmount(member);
  return `${formatDateTR(member.latest_transaction_at)} / ${merchant}${amount ? ` / ${amount}` : ""}`;
}

function topMember(
  members: FamilyMemberFinance[],
  getAmount: (member: FamilyMemberFinance) => number,
): FamilyMemberFinance | null {
  const [first] = [...members].sort((left, right) => getAmount(right) - getAmount(left));
  return first && getAmount(first) > 0 ? first : null;
}

function highlightOrEmpty(
  label: string,
  member: FamilyMemberFinance | null,
  amount: string | null,
  empty: string,
): FamilyHighlight {
  return {
    label,
    name: member?.name ?? "Henüz veri yok",
    detail: amount
      ? `${formatKurus(amountToKurus(amount))} / ${label.toLocaleLowerCase("tr")}`
      : empty,
  };
}

function FamilyHighlights({ highlights }: { highlights: FamilyHighlight[] }) {
  return (
    <div className="grid gap-3 lg:grid-cols-3">
      {highlights.map((highlight) => (
        <div key={highlight.label} className="receipt-tape px-5 py-6">
          <div className="flex items-start gap-3">
            <span className="bg-primary/12 grid h-10 w-10 shrink-0 place-items-center rounded-[1rem] text-primary">
              <Trophy className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase tracking-[0.18em] text-muted-foreground">
                {highlight.label}
              </p>
              <p className="mt-2 truncate font-display text-xl font-black">{highlight.name}</p>
              <p className="mt-1 text-sm leading-6 text-muted-foreground">{highlight.detail}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function FamilyBarComparison({ data }: { data: FamilyChartPoint[] }) {
  if (data.length === 0) {
    return <ChartEmpty title="Gelir/gider grafiği" detail="Bu ay grafik için kayıt yok." />;
  }

  return (
    <figure className="rounded-[1.75rem] border border-border/70 bg-card/80 p-4 shadow-sm">
      <figcaption className="flex items-start justify-between gap-3">
        <div>
          <p className="font-display text-xl font-black">Gelir/gider karşılaştırması</p>
          <p className="mt-1 text-sm text-muted-foreground">Her profil için bu ayın hareketi.</p>
        </div>
        <BarChart3 className="h-5 w-5 text-primary" />
      </figcaption>
      <div className="mt-4 h-72 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            layout="vertical"
            margin={{ top: 8, right: 18, bottom: 8, left: 10 }}
          >
            <CartesianGrid stroke="oklch(var(--border) / 0.55)" horizontal={false} />
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="name"
              width={96}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "oklch(var(--muted-foreground))", fontSize: 11, fontWeight: 700 }}
            />
            <Bar dataKey="income" radius={[0, 8, 8, 0]} barSize={12} fill="oklch(var(--primary))" />
            <Bar dataKey="expense" radius={[0, 8, 8, 0]} barSize={12} fill="oklch(var(--accent))" />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-xs font-bold text-muted-foreground">
        <span className="inline-flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-primary" /> Gelir
        </span>
        <span className="inline-flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-accent" /> Gider
        </span>
      </div>
    </figure>
  );
}

function FamilyExpensePie({ data }: { data: FamilyPiePoint[] }) {
  const total = data.reduce((sum, point) => sum + point.value, 0);
  if (total <= 0) {
    return <ChartEmpty title="Gider dağılımı" detail="Bu ay dağılım çıkaracak gider yok." />;
  }

  return (
    <figure className="rounded-[1.75rem] border border-border/70 bg-card/80 p-4 shadow-sm">
      <figcaption className="flex items-start justify-between gap-3">
        <div>
          <p className="font-display text-xl font-black">Gider dağılımı</p>
          <p className="mt-1 text-sm text-muted-foreground">Aile giderinin kişi bazlı payı.</p>
        </div>
        <ChartPie className="h-5 w-5 text-primary" />
      </figcaption>
      <div className="mt-4 flex flex-wrap items-center gap-5">
        <div className="h-48 w-48 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                dataKey="value"
                nameKey="name"
                innerRadius={42}
                outerRadius={82}
                paddingAngle={2}
                stroke="oklch(var(--card))"
                strokeWidth={2}
              >
                {data.map((point, index) => (
                  <Cell key={`${point.name}-${index}`} fill={chartColor(index)} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
        <ul className="grid min-w-0 flex-1 gap-2 text-xs">
          {data.map((point, index) => {
            const percent = Math.round((point.value / total) * 100);
            return (
              <li
                key={`${point.name}-pie-${index}`}
                className="flex items-center justify-between gap-3"
              >
                <span className="flex min-w-0 items-center gap-2">
                  <span
                    aria-hidden
                    className="h-3 w-3 shrink-0 rounded-full"
                    style={{ backgroundColor: chartColor(index) }}
                  />
                  <span className="min-w-0 truncate font-medium">{point.name}</span>
                </span>
                <span className="font-display font-black tabular-nums">
                  {point.valueFormatted} · %{percent}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </figure>
  );
}

function ChartEmpty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="rounded-[1.75rem] border border-dashed border-border/75 bg-card/70 p-5">
      <p className="font-display text-xl font-black">{title}</p>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{detail}</p>
    </div>
  );
}

function friendlyError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

function ErrorNote({ children }: { children: string }) {
  return (
    <p className="bg-destructive/14 rounded-2xl border border-destructive/35 px-4 py-3 text-sm font-semibold text-foreground shadow-sm">
      {children}
    </p>
  );
}

export function FamilyClient() {
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [overview, setOverview] = useState<FamilyOverview | null>(null);
  const [activeProfile, setLocalActiveProfile] = useState<ActiveProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [updatingChildId, setUpdatingChildId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [childName, setChildName] = useState("");
  const [childBirthDate, setChildBirthDate] = useState("2014-09-05");
  const [childFinanceLevel, setChildFinanceLevel] = useState<FinanceLevel>("child");
  const [childDrafts, setChildDrafts] = useState<Record<string, ChildDraft>>({});
  const [showMemberDetails, setShowMemberDetails] = useState(false);

  const loadFamily = useCallback(async () => {
    setError(null);
    try {
      const [memberData, overviewData] = await Promise.all([
        api<FamilyMember[]>("/api/family", {
          silent: true,
          useActiveProfile: false,
        }),
        api<FamilyOverview>("/api/family/overview", {
          silent: true,
          useActiveProfile: false,
        }),
      ]);
      setMembers(memberData);
      setOverview(overviewData);
    } catch (err) {
      setError(friendlyError(err, "Aile bilgileri yüklenemedi."));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    setLocalActiveProfile(readActiveProfile());
    void loadFamily();
  }, [loadFamily]);

  const parents = useMemo(() => members.filter((member) => member.role === "parent"), [members]);
  const children = useMemo(() => members.filter((member) => member.role === "child"), [members]);
  const familyChartData = useMemo<FamilyChartPoint[]>(() => {
    if (!overview) return [];
    return overview.members.map((member) => {
      const income = Math.max(amountToKurus(member.income), 0);
      const expense = Math.max(amountToKurus(member.expense), 0);
      const balance = amountToKurus(member.balance);
      return {
        name: member.name,
        role: member.role,
        income,
        expense,
        balance,
        incomeFormatted: formatKurus(income),
        expenseFormatted: formatKurus(expense),
        balanceFormatted: formatKurus(balance),
      };
    });
  }, [overview]);
  const expensePieData = useMemo<FamilyPiePoint[]>(
    () =>
      familyChartData
        .filter((point) => point.expense > 0)
        .map((point) => ({
          name: point.name,
          value: point.expense,
          valueFormatted: point.expenseFormatted,
        })),
    [familyChartData],
  );
  const familyHighlights = useMemo<FamilyHighlight[]>(() => {
    const overviewMembers = overview?.members ?? [];
    const topIncome = topMember(overviewMembers, (member) => amountToKurus(member.income));
    const topExpense = topMember(overviewMembers, (member) => amountToKurus(member.expense));
    const topSaver = topMember(overviewMembers, (member) => amountToKurus(member.balance));

    return [
      highlightOrEmpty(
        "En yüksek gelir",
        topIncome,
        topIncome?.income ?? null,
        "Bu ay gelir kaydı yok.",
      ),
      highlightOrEmpty(
        "En yüksek gider",
        topExpense,
        topExpense?.expense ?? null,
        "Bu ay gider kaydı yok.",
      ),
      highlightOrEmpty(
        "En çok biriktiren",
        topSaver,
        topSaver?.balance ?? null,
        "Bu ay pozitif net durum yok.",
      ),
    ];
  }, [overview]);

  async function handleCreateChild() {
    if (!childName.trim() || !childBirthDate) {
      setError("Aile üyesinin adı ve doğum tarihi gerekli.");
      return;
    }

    const payload: ChildCreateInput = {
      name: childName,
      birth_date: childBirthDate,
      finance_level: childFinanceLevel,
    };
    setIsSubmitting(true);
    setError(null);
    try {
      const created = await api<FamilyMember>("/api/family/children", {
        method: "POST",
        body: payload,
        silent: true,
        useActiveProfile: false,
      });
      setMembers((current) => [...current, created]);
      setChildName("");
      setChildBirthDate("2014-09-05");
      setChildFinanceLevel("child");
      void loadFamily();
      toast.success("Aile üyesi profili eklendi.");
    } catch (err) {
      setError(friendlyError(err, "Aile üyesi profili eklenemedi."));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleUpdateChildProfile(child: FamilyMember) {
    const draft = childDrafts[child.id] ?? {
      birthDate: child.birth_date ?? "",
      financeLevel: child.finance_level,
    };
    if (!draft.birthDate) {
      setError("Doğum tarihi boş olamaz.");
      return;
    }
    setUpdatingChildId(child.id);
    setError(null);
    try {
      const updated = await api<FamilyMember>(`/api/family/children/${child.id}`, {
        method: "PATCH",
        body: { birth_date: draft.birthDate, finance_level: draft.financeLevel },
        silent: true,
        useActiveProfile: false,
      });
      setMembers((current) => current.map((item) => (item.id === child.id ? updated : item)));
      void loadFamily();
    } catch (err) {
      setError(friendlyError(err, "Çocuk profili güncellenemedi."));
    } finally {
      setUpdatingChildId(null);
    }
  }

  function updateChildDraft(child: FamilyMember, partial: Partial<ChildDraft>) {
    setChildDrafts((current) => {
      const existing = current[child.id] ?? {
        birthDate: child.birth_date ?? "",
        financeLevel: child.finance_level,
      };
      return {
        ...current,
        [child.id]: { ...existing, ...partial },
      };
    });
  }

  async function handleSwitch(child: FamilyMember) {
    setUpdatingChildId(child.id);
    setError(null);
    try {
      const response = await api<TokenResponse>(`/api/family/switch/${child.id}`, {
        method: "POST",
        silent: true,
        useActiveProfile: false,
      });
      setActiveProfile(response);
      setLocalActiveProfile(readActiveProfile());
      toast.success(`${child.name} profiline geçildi.`);
    } catch (err) {
      setError(friendlyError(err, "Çocuk profiline geçilemedi."));
    } finally {
      setUpdatingChildId(null);
    }
  }

  function handleReturnParent() {
    clearActiveProfile();
    setLocalActiveProfile(null);
    toast.success("Ebeveyn profiline dönüldü.");
  }

  return (
    <div className="space-y-8">
      <section className="grid min-w-0 gap-5 lg:grid-cols-[1fr_0.55fr] lg:items-stretch">
        <div className="ledger-sheet binder-holes p-5 pl-8 sm:p-9 sm:pl-20">
          <div className="relative z-10 max-w-3xl space-y-5">
            <span className="stamp-label bg-background/70">Aile modu</span>
            <h1 className="font-display text-[2.65rem] font-black leading-[0.94] sm:text-5xl lg:text-6xl">
              Aynı evde farklı finans dili.
            </h1>
            <p className="text-foreground/78 max-w-[62ch] text-base leading-7 sm:text-lg sm:leading-8">
              Ebeveyn çocuk profillerini yönetir; çocuk moduna geçince panel ve sohbet o profilin
              güvenli veri kapsamıyla çalışır.
            </p>
          </div>
        </div>

        <aside className="receipt-tape rotate-1 p-6 pt-9">
          <div className="flex items-center gap-3">
            <ShieldCheck className="h-6 w-6 text-primary" />
            <div>
              <p className="font-display text-2xl font-black">Veri sınırı görünür</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Çocuk kendi kayıtlarını görür; ebeveyn aile toplamını yönetir.
              </p>
            </div>
          </div>
        </aside>
      </section>

      {error ? <ErrorNote>{error}</ErrorNote> : null}

      {overview ? (
        <section className="space-y-5">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="eyebrow">Aile finans özeti</p>
              <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
                Ebeveyn görünümü
              </h2>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setShowMemberDetails((current) => !current)}
              >
                {showMemberDetails ? "Kişi detayını gizle" : "Kişi detayını aç"}
              </Button>
              <span className="stamp-label bg-card/70 text-muted-foreground">Yalnızca ebeveyn</span>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
            {(
              [
                {
                  label: "Aile geliri",
                  value: overview.total_income,
                  detail: "Bu ay görünen toplam gelir",
                },
                {
                  label: "Aile gideri",
                  value: overview.total_expense,
                  detail: "Bu ay görünen toplam gider",
                },
                {
                  label: "Net aile durumu",
                  value: overview.total_balance,
                  detail: "Gelir eksi gider",
                },
                {
                  label: "Aylık tekrar",
                  value: overview.total_recurring_monthly,
                  detail: "Aktif abonelik ve faturalar",
                },
              ] satisfies FamilyMetricCard[]
            ).map(({ label, value, detail }) => (
              <div key={label} className="cash-envelope p-5">
                <div className="relative z-10 space-y-4">
                  <p className="text-sm font-bold text-secondary-foreground/80">{label}</p>
                  <p className="break-words font-display text-[2rem] font-black tabular-nums leading-none">
                    {formatKurus(amountToKurus(value))}
                  </p>
                  <p className="text-sm leading-6 text-muted-foreground">{detail}</p>
                </div>
              </div>
            ))}
          </div>

          <FamilyHighlights highlights={familyHighlights} />

          <div className="grid gap-3 xl:grid-cols-3">
            {overview.members.map((member) => (
              <div key={member.user_id} className="receipt-tape px-5 py-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <span className="stamp-label bg-background/70">
                      {member.role === "parent" ? "Ebeveyn" : "Çocuk"}
                    </span>
                    <p className="mt-3 truncate font-display text-xl font-black">{member.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {member.age !== null ? `${member.age} yaş / ` : ""}
                      {member.age_status ? `${ageStatusLabels[member.age_status]} / ` : ""}
                      {member.transaction_count} işlem
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-xs font-bold uppercase tracking-[0.16em] text-muted-foreground">
                      Net
                    </p>
                    <p className="font-display text-lg font-black tabular-nums">
                      {formatKurus(amountToKurus(member.balance))}
                    </p>
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <p className="font-bold text-muted-foreground">Gelir</p>
                    <p className="font-display font-black tabular-nums">
                      {formatKurus(amountToKurus(member.income))}
                    </p>
                  </div>
                  <div>
                    <p className="font-bold text-muted-foreground">Gider</p>
                    <p className="font-display font-black tabular-nums">
                      {formatKurus(amountToKurus(member.expense))}
                    </p>
                  </div>

                  {showMemberDetails ? (
                    <>
                      <div>
                        <p className="font-bold text-muted-foreground">Gider payı</p>
                        <p className="font-display font-black tabular-nums">
                          {formatExpenseShare(member.expense_share_percent)}
                        </p>
                      </div>
                      <div>
                        <p className="font-bold text-muted-foreground">Fiş işlemi</p>
                        <p className="font-display font-black tabular-nums">
                          {member.receipt_transaction_count}
                        </p>
                      </div>
                      <div className="col-span-2 grid grid-cols-2 gap-3 border-t border-dashed border-border pt-3">
                        <div>
                          <p className="font-bold text-muted-foreground">Aylık tekrar</p>
                          <p className="font-display font-black tabular-nums">
                            {formatKurus(amountToKurus(member.recurring_monthly))}
                          </p>
                        </div>
                        <div>
                          <p className="font-bold text-muted-foreground">Aktif tekrar</p>
                          <p className="font-display font-black tabular-nums">
                            {member.recurring_count}
                          </p>
                        </div>
                      </div>
                    </>
                  ) : null}
                </div>

                {showMemberDetails ? (
                  <div className="mt-4 rounded-[1rem] border border-border/65 bg-background/55 px-3 py-2 text-sm leading-6">
                    <p className="font-bold text-muted-foreground">Son hareket</p>
                    <p className="font-semibold">{latestTransactionText(member)}</p>
                  </div>
                ) : null}
              </div>
            ))}
          </div>

          {showMemberDetails ? (
            <div className="grid gap-4 xl:grid-cols-[1.08fr_0.92fr]">
              <FamilyBarComparison data={familyChartData} />
              <FamilyExpensePie data={expensePieData} />
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="grid min-w-0 gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="ledger-sheet p-5 sm:p-8">
          <div className="relative z-10 space-y-5">
            <div>
              <p className="eyebrow">Çocuk profili</p>
              <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
                Yeni profil ekle
              </h2>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-2">
                <label htmlFor="child-name" className="text-sm font-medium">
                  Ad
                </label>
                <Input
                  id="child-name"
                  value={childName}
                  onChange={(event) => setChildName(event.target.value)}
                  placeholder="Çocuğun adı"
                />
              </div>
              <div className="space-y-2">
                <label htmlFor="child-birth-date" className="text-sm font-medium">
                  Doğum tarihi
                </label>
                <Input
                  id="child-birth-date"
                  type="date"
                  value={childBirthDate}
                  onChange={(event) => {
                    const next = event.target.value;
                    setChildBirthDate(next);
                    setChildFinanceLevel(suggestedFinanceLevel(next));
                  }}
                />
              </div>
            </div>
            <select
              className={selectClassName}
              value={childFinanceLevel}
              onChange={(event) => setChildFinanceLevel(event.target.value as FinanceLevel)}
            >
              {Object.entries(financeLevelLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            <Button
              type="button"
              className="w-full"
              disabled={isSubmitting}
              onClick={() => void handleCreateChild()}
            >
              {isSubmitting ? "Ekleniyor..." : "Aile üyesi ekle"}
              <UserPlus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Aile kayıtları</p>
              <h2 className="mt-2 font-display text-[2rem] font-black leading-none sm:text-3xl">
                Profiller
              </h2>
            </div>
            <Users className="h-7 w-7 text-primary" />
          </div>

          {isLoading ? (
            <div className="receipt-tape flex items-center gap-3 px-5 py-6 text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Aile bilgileri yükleniyor...
            </div>
          ) : (
            <div className="space-y-3">
              {parents.map((parent, index) => (
                <div key={parent.id} className="cash-envelope p-5">
                  <div className="relative z-10 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <span className="stamp-label bg-background/70">Ebeveyn</span>
                      <p className="mt-3 truncate font-display text-xl font-black">{parent.name}</p>
                      <p className="text-sm text-muted-foreground">
                        Aile yöneticisi / {memberAgeText(parent)}
                      </p>
                    </div>
                    {activeProfile && index === 0 ? (
                      <Button
                        type="button"
                        variant="secondary"
                        className="w-full sm:w-auto"
                        onClick={handleReturnParent}
                      >
                        Ebeveyne dön
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))}

              {children.length === 0 ? (
                <div className="receipt-tape px-5 py-8">
                  <Baby className="h-6 w-6 text-primary" />
                  <h3 className="mt-4 font-display text-2xl font-black">Henüz çocuk profili yok</h3>
                  <p className="mt-2 text-sm leading-6 text-muted-foreground">
                    Bir çocuk profili eklediğinde panel ve sohbet için ayrı güvenli kapsam oluşur.
                  </p>
                </div>
              ) : (
                children.map((child) => {
                  const isActive = activeProfile?.user.id === child.id;
                  const isUpdating = updatingChildId === child.id;
                  const draft = childDrafts[child.id] ?? {
                    birthDate: child.birth_date ?? "",
                    financeLevel: child.finance_level,
                  };
                  return (
                    <div key={child.id} className="receipt-tape space-y-5 px-5 py-6">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                        <div className="min-w-0">
                          <p className="min-w-0 truncate font-display text-xl font-black">
                            {child.name}
                          </p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            Aile çocuğu / {memberAgeText(child)}
                          </p>
                        </div>
                        {isActive ? (
                          <span className="badge-active shrink-0">
                            <Baby className="h-3.5 w-3.5" />
                            Aktif profil
                          </span>
                        ) : null}
                      </div>

                      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                        <Input
                          type="date"
                          value={draft.birthDate}
                          aria-label={`${child.name} doğum tarihi`}
                          onChange={(event) =>
                            updateChildDraft(child, { birthDate: event.target.value })
                          }
                        />
                        <select
                          className={selectClassName}
                          value={draft.financeLevel}
                          aria-label={`${child.name} finans dili`}
                          onChange={(event) =>
                            updateChildDraft(child, {
                              financeLevel: event.target.value as FinanceLevel,
                            })
                          }
                        >
                          {Object.entries(financeLevelLabels).map(([value, label]) => (
                            <option key={value} value={value}>
                              {label}
                            </option>
                          ))}
                        </select>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="min-h-11"
                          disabled={isUpdating}
                          onClick={() => void handleUpdateChildProfile(child)}
                        >
                          Kaydet
                          <Edit3 className="h-4 w-4" />
                        </Button>
                      </div>

                      <Button
                        type="button"
                        variant={isActive ? "secondary" : "default"}
                        className="w-full"
                        disabled={isUpdating || isActive}
                        onClick={() => void handleSwitch(child)}
                      >
                        {isUpdating
                          ? "Geçiliyor..."
                          : isActive
                            ? "Bu profilde aktifsin"
                            : "Bu profile geç"}
                      </Button>
                    </div>
                  );
                })
              )}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
