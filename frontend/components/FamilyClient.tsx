"use client";

import { Baby, Edit3, Loader2, ShieldCheck, UserPlus, Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import {
  clearActiveProfile,
  readActiveProfile,
  setActiveProfile,
  type ActiveProfile,
} from "@/lib/active-profile";
import type { ChildCreateInput, FamilyMember, TokenResponse } from "@/lib/types";

const selectClassName =
  "flex h-11 w-full rounded-2xl border border-input bg-background/80 px-4 py-2 text-sm ring-offset-background transition-all duration-200 ease-quint focus-visible:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

function friendlyError(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.detail : fallback;
}

export function FamilyClient() {
  const [members, setMembers] = useState<FamilyMember[]>([]);
  const [activeProfile, setLocalActiveProfile] = useState<ActiveProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [updatingChildId, setUpdatingChildId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [childName, setChildName] = useState("");
  const [childAge, setChildAge] = useState("12");

  const loadFamily = useCallback(async () => {
    setError(null);
    try {
      const data = await api<FamilyMember[]>("/api/family", {
        silent: true,
        useActiveProfile: false,
      });
      setMembers(data);
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

  const parent = useMemo(() => members.find((member) => member.role === "parent"), [members]);
  const children = useMemo(() => members.filter((member) => member.role === "child"), [members]);

  async function handleCreateChild() {
    const age = Number.parseInt(childAge, 10);
    if (!childName.trim() || !Number.isFinite(age)) {
      setError("Çocuk adı ve yaşı gerekli.");
      return;
    }

    const payload: ChildCreateInput = {
      name: childName,
      age,
      finance_level: "child",
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
      setChildAge("12");
      toast.success("Çocuk profili eklendi.");
    } catch (err) {
      setError(friendlyError(err, "Çocuk profili eklenemedi."));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleAgeStep(child: FamilyMember, delta: number) {
    const nextAge = Math.max(5, Math.min(17, (child.age ?? 12) + delta));
    setUpdatingChildId(child.id);
    setError(null);
    try {
      const updated = await api<FamilyMember>(`/api/family/children/${child.id}`, {
        method: "PATCH",
        body: { age: nextAge },
        silent: true,
        useActiveProfile: false,
      });
      setMembers((current) => current.map((item) => (item.id === child.id ? updated : item)));
    } catch (err) {
      setError(friendlyError(err, "Çocuk profili güncellenemedi."));
    } finally {
      setUpdatingChildId(null);
    }
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
      <section className="grid gap-5 lg:grid-cols-[1fr_0.55fr] lg:items-stretch">
        <div className="ledger-sheet binder-holes p-6 pl-8 sm:p-9 sm:pl-20">
          <div className="relative z-10 max-w-3xl space-y-5">
            <span className="stamp-label bg-background/70">Aile modu</span>
            <h1 className="font-display text-[clamp(2.4rem,5.6vw,5.3rem)] font-black leading-[0.94] tracking-[-0.05em]">
              Aynı evde farklı finans dili.
            </h1>
            <p className="max-w-[62ch] text-lg leading-8 text-muted-foreground">
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

      {error ? (
        <p className="rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm font-medium text-destructive">
          {error}
        </p>
      ) : null}

      <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="ledger-sheet p-6 sm:p-8">
          <div className="relative z-10 space-y-5">
            <div>
              <p className="eyebrow">Çocuk profili</p>
              <h2 className="mt-2 font-display text-3xl font-black tracking-[-0.04em]">
                Yeni profil ekle
              </h2>
            </div>
            <div className="grid gap-3 sm:grid-cols-[1fr_7rem]">
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
                <label htmlFor="child-age" className="text-sm font-medium">
                  Yaş
                </label>
                <Input
                  id="child-age"
                  type="number"
                  min={5}
                  max={17}
                  value={childAge}
                  onChange={(event) => setChildAge(event.target.value)}
                />
              </div>
            </div>
            <select className={selectClassName} value="child" disabled>
              <option value="child">Çocuk koç dili</option>
            </select>
            <Button
              type="button"
              className="w-full"
              disabled={isSubmitting}
              onClick={() => void handleCreateChild()}
            >
              {isSubmitting ? "Ekleniyor..." : "Çocuk profili ekle"}
              <UserPlus className="h-4 w-4" />
            </Button>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="eyebrow">Aile kayıtları</p>
              <h2 className="mt-2 font-display text-3xl font-black tracking-[-0.04em]">
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
              {parent ? (
                <div className="cash-envelope p-5">
                  <div className="relative z-10 flex items-start justify-between gap-4">
                    <div>
                      <span className="stamp-label bg-background/70">Ebeveyn</span>
                      <p className="mt-3 font-display text-xl font-black">{parent.name}</p>
                      <p className="text-sm text-muted-foreground">Aile yöneticisi</p>
                    </div>
                    {activeProfile ? (
                      <Button type="button" variant="secondary" onClick={handleReturnParent}>
                        Ebeveyne dön
                      </Button>
                    ) : null}
                  </div>
                </div>
              ) : null}

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
                  return (
                    <div key={child.id} className="receipt-tape px-5 py-6">
                      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-display text-xl font-black">{child.name}</p>
                            {isActive ? (
                              <span className="stamp-label bg-primary text-primary-foreground">
                                Aktif çocuk modu
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {child.age ?? 12} yaş / çocuk koç dili
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={isUpdating}
                            onClick={() => void handleAgeStep(child, -1)}
                          >
                            - Yaş
                            <Edit3 className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={isUpdating}
                            onClick={() => void handleAgeStep(child, 1)}
                          >
                            + Yaş
                            <Edit3 className="h-4 w-4" />
                          </Button>
                          <Button
                            type="button"
                            size="sm"
                            disabled={isUpdating || isActive}
                            onClick={() => void handleSwitch(child)}
                          >
                            {isUpdating ? "Geçiliyor..." : "Bu profile geç"}
                          </Button>
                        </div>
                      </div>
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
