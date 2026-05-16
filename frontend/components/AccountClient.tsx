"use client";

import { BrainCircuit, Loader2, Save, ShieldCheck } from "lucide-react";
import { useSession } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import type { AccountUpdateInput, AgeStatus, AuthUser, FinanceLevel } from "@/lib/types";

const selectClassName =
  "flex h-11 w-full rounded-2xl border border-input bg-background/80 px-4 py-2 text-sm ring-offset-background transition-all duration-200 ease-quint focus-visible:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2";

const financeLevelLabels: Record<Exclude<FinanceLevel, "child">, string> = {
  beginner: "Başlangıç",
  intermediate: "Orta",
  advanced: "İleri",
};

const ageStatusLabels: Record<AgeStatus, string> = {
  minor: "18 yaş altı",
  adult: "Yetişkin",
};

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

export function AccountClient() {
  const router = useRouter();
  const { data: session, update } = useSession();
  const user = session?.user;
  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");
  const [birthDate, setBirthDate] = useState(user?.birthDate ?? "");
  const [financeLevel, setFinanceLevel] = useState<Exclude<FinanceLevel, "child">>(
    user?.financeLevel === "child" ? "beginner" : (user?.financeLevel ?? "beginner"),
  );
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    setName(user.name ?? "");
    setEmail(user.email ?? "");
    setBirthDate(user.birthDate ?? "");
    setFinanceLevel(user.financeLevel === "child" ? "beginner" : user.financeLevel);
  }, [user]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSaving(true);

    if (birthDate && new Date(birthDate) > new Date()) {
      setError("Doğum tarihi gelecekte olamaz.");
      setIsSaving(false);
      return;
    }
    if ((currentPassword && !newPassword) || (!currentPassword && newPassword)) {
      setError("Şifre değiştirmek için mevcut ve yeni şifre birlikte gerekli.");
      setIsSaving(false);
      return;
    }

    const payload: AccountUpdateInput = {
      name,
      email,
      birth_date: birthDate || null,
      finance_level: financeLevel,
    };
    if (currentPassword && newPassword) {
      payload.current_password = currentPassword;
      payload.new_password = newPassword;
    }

    try {
      const updated = await api<AuthUser>("/api/auth/me", {
        method: "PATCH",
        body: payload,
        silent: true,
        useActiveProfile: false,
      });
      await update({
        user: {
          id: updated.id,
          email: updated.email,
          name: updated.name,
          role: updated.role,
          parentId: updated.parent_id,
          familyId: updated.family_id,
          birthDate: updated.birth_date,
          age: updated.age,
          ageStatus: updated.age_status,
          financeLevel: updated.finance_level,
          isDemo: updated.is_demo,
        },
      });
      setCurrentPassword("");
      setNewPassword("");
      router.refresh();
      toast.success("Hesap bilgileri güncellendi.");
    } catch (err) {
      setError(friendlyError(err, "Hesap bilgileri güncellenemedi."));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="page-enter space-y-8">
      <section className="grid min-w-0 gap-5 lg:grid-cols-[1fr_0.5fr] lg:items-stretch">
        <div className="ledger-sheet binder-holes p-5 pl-8 sm:p-9 sm:pl-20">
          <div className="relative z-10 max-w-3xl space-y-5">
            <span className="stamp-label bg-background/70">Hesap ayarları</span>
            <h1 className="font-display text-[2.65rem] font-black leading-[0.94] sm:text-5xl lg:text-6xl">
              Profil bilgilerini güncelle.
            </h1>
            <p className="text-foreground/78 max-w-[62ch] text-base leading-7 sm:text-lg sm:leading-8">
              Ad, e-posta, doğum tarihi, finans seviyesi ve şifre bilgileri buradan değişir. Yaş
              doğum tarihinden otomatik hesaplanır.
            </p>
          </div>
        </div>

        <aside className="receipt-tape rotate-1 p-6 pt-9">
          <div className="flex items-center gap-3">
            <ShieldCheck className="h-6 w-6 text-primary" />
            <div>
              <p className="font-display text-2xl font-black">Güvenli güncelleme</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Şifre değiştirmek için mevcut şifre doğrulanır; yaş statüsü manuel değil doğum
                tarihinden hesaplanır.
              </p>
              <Button asChild variant="outline" size="sm" className="mt-4">
                <Link href="/account/memory">
                  <BrainCircuit className="h-4 w-4" />
                  Koç hafızasını gör
                </Link>
              </Button>
            </div>
          </div>
        </aside>
      </section>

      {error ? <ErrorNote>{error}</ErrorNote> : null}

      <form className="ledger-sheet max-w-4xl p-5 sm:p-8" onSubmit={handleSubmit}>
        <div className="relative z-10 space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor="account-name" className="text-sm font-medium">
                Ad soyad
              </label>
              <Input
                id="account-name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="account-email" className="text-sm font-medium">
                E-posta
              </label>
              <Input
                id="account-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor="account-birth-date" className="text-sm font-medium">
                Doğum tarihi
              </label>
              <Input
                id="account-birth-date"
                type="date"
                value={birthDate}
                onChange={(event) => setBirthDate(event.target.value)}
                placeholder="İsteğe bağlı"
              />
              <p className="text-xs font-medium text-muted-foreground">
                {user?.age !== null && user?.age !== undefined
                  ? `${user.age} yaş / ${
                      user.ageStatus ? ageStatusLabels[user.ageStatus] : "Statü hesaplanıyor"
                    }`
                  : "Yaş otomatik hesaplanır."}
              </p>
            </div>
            <div className="space-y-2">
              <label htmlFor="account-finance-level" className="text-sm font-medium">
                Finans seviyesi
              </label>
              <select
                id="account-finance-level"
                className={selectClassName}
                value={financeLevel}
                onChange={(event) =>
                  setFinanceLevel(event.target.value as Exclude<FinanceLevel, "child">)
                }
              >
                {Object.entries(financeLevelLabels).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="bg-background/72 grid gap-4 rounded-[1.5rem] border border-dashed border-primary/30 p-4 md:grid-cols-2">
            <div className="space-y-2">
              <label htmlFor="account-current-password" className="text-sm font-medium">
                Mevcut şifre
              </label>
              <Input
                id="account-current-password"
                type="password"
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
                placeholder="Şifre değişecekse"
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="account-new-password" className="text-sm font-medium">
                Yeni şifre
              </label>
              <Input
                id="account-new-password"
                type="password"
                minLength={8}
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                placeholder="En az 8 karakter"
              />
            </div>
          </div>

          <Button type="submit" className="w-full md:w-auto" disabled={isSaving}>
            {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            {isSaving ? "Kaydediliyor..." : "Bilgileri kaydet"}
          </Button>
        </div>
      </form>
    </div>
  );
}
