"use client";

import { Baby, Edit3, Loader2, ShieldCheck, UserPlus, Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { amountToKurus, formatKurus } from "@/lib/format";
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
            <span className="stamp-label bg-card/70 text-muted-foreground">Yalnızca ebeveyn</span>
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
                  <p className="shrink-0 font-display text-lg font-black tabular-nums">
                    {formatKurus(amountToKurus(member.balance))}
                  </p>
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
                  <div className="col-span-2">
                    <p className="font-bold text-muted-foreground">Aylık tekrar</p>
                    <p className="font-display font-black tabular-nums">
                      {formatKurus(amountToKurus(member.recurring_monthly))}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
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
