"use client";

import {
  BrainCircuit,
  Download,
  Loader2,
  Mail,
  Save,
  ShieldAlert,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import type { Session } from "next-auth";
import { signOut, useSession } from "next-auth/react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { type FormEvent, useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { api, ApiError, apiDownload } from "@/lib/api";
import { clearActiveProfile } from "@/lib/active-profile";
import type { AccountUpdateInput, AgeStatus, AuthUser, FinanceLevel } from "@/lib/types";

type SessionUser = Session["user"];

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

      <DataExportSection />

      <EmailSummarySection email={user?.email} />

      <DangerZoneSection user={user} />
    </div>
  );
}

function nextMondayLabel(): string {
  const today = new Date();
  const day = today.getDay();
  const daysUntilMonday = day === 1 ? 7 : (8 - day) % 7 || 7;
  const next = new Date(today);
  next.setDate(today.getDate() + daysUntilMonday);
  return new Intl.DateTimeFormat("tr-TR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
  }).format(next);
}

const EMAIL_SUMMARY_STORAGE_KEY = "cuzdan-kocu.email-summary.enabled";

function EmailSummarySection({ email }: { email: string | null | undefined }) {
  const [enabled, setEnabled] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      setEnabled(window.localStorage.getItem(EMAIL_SUMMARY_STORAGE_KEY) === "on");
    } catch {
      // ignore localStorage failures; toggle just stays off.
    } finally {
      setHydrated(true);
    }
  }, []);

  function handleToggle() {
    setEnabled((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(EMAIL_SUMMARY_STORAGE_KEY, next ? "on" : "off");
      } catch {
        // best-effort persistence
      }
      toast.success(
        next ? "Haftalık özet e-postası planlandı." : "Haftalık özet e-postası kapatıldı.",
      );
      return next;
    });
  }

  return (
    <section className="ledger-sheet max-w-4xl p-5 sm:p-8">
      <div className="relative z-10 grid gap-4 md:grid-cols-[1fr_auto] md:items-center">
        <div>
          <span className="stamp-label bg-background/70">Haftalık özet</span>
          <h2 className="mt-3 font-display text-3xl font-black tracking-tight">
            Pazartesi sabahı özet e-postası
          </h2>
          <p className="mt-2 max-w-[58ch] text-sm leading-6 text-muted-foreground">
            Açık olduğunda haftanın geliri, gideri, en yüksek üç kategorisi ve hedef ilerlemen
            pazartesi sabahı kısa bir e-posta olarak gelir.
            {email ? (
              <>
                {" "}
                Gönderim adresi: <strong className="font-bold">{email}</strong>.
              </>
            ) : null}
          </p>
          <p className="mt-3 text-xs text-muted-foreground">
            {enabled
              ? `Sonraki gönderim yaklaşık ${nextMondayLabel()}.`
              : "Demo aşamasında gerçek e-posta gönderilmez; bu tercih yalnızca tarayıcına kaydedilir."}
          </p>
        </div>
        <Button
          type="button"
          variant={enabled ? "default" : "outline"}
          onClick={handleToggle}
          disabled={!hydrated}
          className="md:justify-self-end"
          aria-pressed={enabled}
        >
          <Mail className="h-4 w-4" />
          {enabled ? "Açık" : "Kapalı"}
        </Button>
      </div>
    </section>
  );
}

function formatTodayStamp(): string {
  const today = new Date();
  const year = today.getFullYear();
  const month = String(today.getMonth() + 1).padStart(2, "0");
  const day = String(today.getDate()).padStart(2, "0");
  return `${year}${month}${day}`;
}

function DataExportSection() {
  const [isDownloading, setIsDownloading] = useState(false);

  async function handleDownload() {
    setIsDownloading(true);
    try {
      const filename = `cuzdan-kocu-verim-${formatTodayStamp()}.zip`;
      await apiDownload("/api/exports/all.zip", filename);
      toast.success("Verilerin indirildi.");
    } catch (err) {
      toast.error(
        err instanceof ApiError
          ? err.detail
          : "Verilerin indirilemedi, biraz sonra tekrar dener misin?",
      );
    } finally {
      setIsDownloading(false);
    }
  }

  return (
    <section className="ledger-sheet max-w-4xl p-5 sm:p-8">
      <div className="relative z-10 grid gap-4 md:grid-cols-[1fr_auto] md:items-center">
        <div>
          <span className="stamp-label bg-background/70">Verim benim</span>
          <h2 className="mt-3 font-display text-3xl font-black tracking-tight">Verilerimi indir</h2>
          <p className="mt-2 max-w-[58ch] text-sm leading-6 text-muted-foreground">
            Tüm işlemlerini, aboneliklerini ve hedeflerini tek ZIP içinde dışa aktarabilirsin. Excel
            uyumlu CSV, Türkçe karakterler korunur.
          </p>
        </div>
        <Button
          type="button"
          onClick={handleDownload}
          disabled={isDownloading}
          className="md:justify-self-end"
        >
          {isDownloading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          {isDownloading ? "Hazırlanıyor..." : "Verilerimi indir (ZIP)"}
        </Button>
      </div>
    </section>
  );
}

function DangerZoneSection({ user }: { user: SessionUser | undefined }) {
  const [isOpen, setIsOpen] = useState(false);
  const isDemo = user?.isDemo === true;

  return (
    <>
      <section className="bg-destructive/8 max-w-4xl rounded-[1.5rem] border border-destructive/35 p-5 sm:p-8">
        <div className="space-y-4">
          <div className="flex items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-destructive/15 text-destructive">
              <ShieldAlert className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <h2 className="font-display text-2xl font-black tracking-tight">Tehlikeli bölge</h2>
              <p className="mt-1 max-w-[58ch] text-sm leading-6 text-muted-foreground">
                Hesabını sildiğinde tüm işlemlerin, fişlerin, hedeflerin, aboneliklerin ve hafıza
                notların kalıcı olarak silinir. Bu işlem geri alınamaz.
              </p>
            </div>
          </div>

          {isDemo ? (
            <p className="rounded-2xl border border-destructive/30 bg-background/70 px-4 py-3 text-sm font-semibold text-foreground">
              Demo hesabı silinemez. Demo hesaplar jüri ve sunum için korunur.
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="destructive"
              onClick={() => setIsOpen(true)}
              disabled={isDemo}
              title={isDemo ? "Demo hesabı silinemez." : undefined}
            >
              <Trash2 className="h-4 w-4" />
              Hesabımı sil
            </Button>
          </div>
        </div>
      </section>

      <DeleteAccountDialog open={isOpen} onOpenChange={setIsOpen} user={user} />
    </>
  );
}

function DeleteAccountDialog({
  open,
  onOpenChange,
  user,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: SessionUser | undefined;
}) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setCurrentPassword("");
      setError(null);
      setIsSubmitting(false);
    }
  }, [open]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await api<void>("/api/auth/me", {
        method: "DELETE",
        body: { current_password: currentPassword },
        silent: true,
      });
      clearActiveProfile();
      toast.success("Hesabın silindi.");
      await signOut({ callbackUrl: "/login" });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Hesap silinemedi, tekrar dener misin?");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  const isParent = user?.role === "parent";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Hesabını silmek istediğine emin misin?</DialogTitle>
          <DialogDescription>
            Bu işlem geri alınamaz. Tüm işlemlerin, fişlerin, hedeflerin, aboneliklerin ve hafıza
            notların silinecek.
          </DialogDescription>
        </DialogHeader>

        {isParent ? (
          <p className="rounded-xl border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs font-semibold text-foreground">
            Çocuk profilleri ve onlara ait tüm veriler de silinecek.
          </p>
        ) : null}

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div className="space-y-2">
            <label htmlFor="delete-account-password" className="text-sm font-medium">
              Mevcut şifre
            </label>
            <Input
              id="delete-account-password"
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              autoComplete="current-password"
              required
            />
          </div>

          {error ? (
            <p className="bg-destructive/14 rounded-2xl border border-destructive/35 px-4 py-3 text-sm font-semibold text-foreground">
              {error}
            </p>
          ) : null}

          <DialogFooter className="gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
            >
              Vazgeç
            </Button>
            <Button type="submit" variant="destructive" disabled={isSubmitting}>
              {isSubmitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              Hesabımı kalıcı olarak sil
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
