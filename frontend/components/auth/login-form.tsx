"use client";

import { ArrowRight, Baby, Sparkles, UserRound, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { DemoAccount, UserRole } from "@/lib/types";

function callbackUrlFromLocation(): string {
  if (typeof window === "undefined") return "/dashboard";
  const raw = new URLSearchParams(window.location.search).get("callbackUrl");
  return raw?.startsWith("/") ? raw : "/dashboard";
}

type DemoBucket = {
  key: "parent" | "minor_child" | "adult_child" | "individual";
  title: string;
  icon: typeof Users;
  helper: string;
  accounts: DemoAccount[];
};

function bucketFor(account: DemoAccount): DemoBucket["key"] {
  if (account.role === "parent") return "parent";
  if (account.role === "child") {
    return account.age_status === "minor" ? "minor_child" : "adult_child";
  }
  return "individual";
}

const BUCKET_META: Record<DemoBucket["key"], Pick<DemoBucket, "title" | "icon" | "helper">> = {
  parent: {
    title: "Aile — Ebeveynler",
    helper: "Tüm aile verilerini görür",
    icon: Users,
  },
  minor_child: {
    title: "Aile — 18 yaş altı çocuklar",
    helper: "Otomatik çocuk lite mod",
    icon: Baby,
  },
  adult_child: {
    title: "Aile — 18 yaş üstü çocuklar",
    helper: "Yetişkin çocuk, klasik arayüz",
    icon: Sparkles,
  },
  individual: {
    title: "Bireysel hesap",
    helper: "Aileden bağımsız",
    icon: UserRound,
  },
};

const BUCKET_ORDER: DemoBucket["key"][] = ["parent", "minor_child", "adult_child", "individual"];

const roleAccent: Record<UserRole, string> = {
  parent: "border-primary/40 bg-primary/10",
  child: "border-accent/45 bg-accent/15",
  individual: "border-secondary/55 bg-secondary/25",
};

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("ayse@demo.cuzdan-kocu.app");
  const [password, setPassword] = useState("demo123");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [demoAccounts, setDemoAccounts] = useState<DemoAccount[]>([]);
  const [demoLoadError, setDemoLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const accounts = await api<DemoAccount[]>("/api/auth/demo-accounts", {
          silent: true,
        });
        if (!cancelled) setDemoAccounts(accounts);
      } catch {
        if (!cancelled) {
          setDemoLoadError("Demo hesaplar yüklenemedi, e-posta ile giriş yapabilirsin.");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const buckets = useMemo<DemoBucket[]>(() => {
    if (demoAccounts.length === 0) return [];
    const grouped = new Map<DemoBucket["key"], DemoAccount[]>();
    for (const account of demoAccounts) {
      const key = bucketFor(account);
      const list = grouped.get(key) ?? [];
      list.push(account);
      grouped.set(key, list);
    }
    return BUCKET_ORDER.filter((key) => grouped.has(key)).map((key) => ({
      key,
      title: BUCKET_META[key].title,
      icon: BUCKET_META[key].icon,
      helper: BUCKET_META[key].helper,
      accounts: grouped.get(key) ?? [],
    }));
  }, [demoAccounts]);

  async function signInWith(targetEmail: string, targetPassword: string): Promise<void> {
    setError(null);
    setIsSubmitting(true);
    const callbackUrl = callbackUrlFromLocation();
    const result = await signIn("credentials", {
      email: targetEmail,
      password: targetPassword,
      callbackUrl,
      redirect: false,
    });
    setIsSubmitting(false);
    if (result?.ok) {
      router.push(result.url ?? callbackUrl);
      router.refresh();
      return;
    }
    setError("E-posta veya şifre hatalı.");
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await signInWith(email, password);
  }

  async function handleDemoClick(account: DemoAccount) {
    setEmail(account.email);
    setPassword(account.password);
    await signInWith(account.email, account.password);
  }

  return (
    <div
      className={cn(
        "grid gap-5",
        buckets.length > 0
          ? "xl:grid-cols-[minmax(0,1.25fr)_minmax(18rem,0.85fr)] xl:items-start"
          : "",
      )}
    >
      {buckets.length > 0 ? (
        <section
          aria-labelledby="demo-accounts-heading"
          className="min-w-0 space-y-4 rounded-[1.5rem] border border-border/70 bg-background/55 p-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3
                id="demo-accounts-heading"
                className="font-display text-lg font-black tracking-[-0.02em]"
              >
                Demo hesap seç
              </h3>
              <p className="text-xs text-muted-foreground">
                Tek tıkla giriş yap, her perspektiften deneyebilirsin.
              </p>
            </div>
            <span className="stamp-label bg-background/70 text-primary">Demo</span>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
            {buckets.map((bucket) => {
              const Icon = bucket.icon;
              return (
                <div key={bucket.key} className="min-w-0 space-y-2">
                  <div className="flex min-w-0 items-center gap-2 text-xs font-bold text-muted-foreground">
                    <Icon className="h-3.5 w-3.5 text-primary" />
                    <span className="min-w-0 truncate">{bucket.title}</span>
                    <span className="font-medium text-muted-foreground/70">·</span>
                    <span className="min-w-0 truncate font-medium text-muted-foreground/70">
                      {bucket.helper}
                    </span>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-1 lg:grid-cols-2 xl:grid-cols-2 2xl:grid-cols-1">
                    {bucket.accounts.map((account) => (
                      <button
                        key={account.email}
                        type="button"
                        disabled={isSubmitting}
                        onClick={() => void handleDemoClick(account)}
                        className={cn(
                          "group min-w-0 rounded-2xl border px-3 py-3 text-left transition-all duration-200 ease-quint hover:-translate-y-0.5 hover:shadow-md disabled:cursor-not-allowed disabled:opacity-60",
                          roleAccent[account.role],
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-display text-sm font-black tracking-[-0.01em]">
                            {account.name}
                          </span>
                          {account.age !== null ? (
                            <span className="rounded-full bg-background/70 px-2 py-0.5 text-[0.65rem] font-bold text-muted-foreground">
                              {account.age} yaş
                            </span>
                          ) : null}
                        </div>
                        <p className="truncate text-xs text-muted-foreground">{account.tagline}</p>
                        <p className="truncate text-[0.65rem] font-medium text-muted-foreground/80">
                          {account.email}
                        </p>
                      </button>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      ) : demoLoadError ? (
        <p className="rounded-2xl border border-border/60 bg-muted/40 px-4 py-3 text-xs text-muted-foreground">
          {demoLoadError}
        </p>
      ) : null}

      <form className="min-w-0 space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label htmlFor="email" className="text-sm font-medium">
            E-posta
          </label>
          <Input
            id="email"
            type="email"
            placeholder="ornek@cuzdan-kocu.app"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />
        </div>
        <div className="space-y-2">
          <label htmlFor="password" className="text-sm font-medium">
            Şifre
          </label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
        </div>

        {error ? (
          <p className="bg-destructive/14 rounded-2xl border border-destructive/35 px-4 py-3 text-sm font-semibold text-foreground shadow-sm">
            {error}
          </p>
        ) : null}

        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? "Giriş yapılıyor..." : "Giriş yap"}
          <ArrowRight className="h-4 w-4" />
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          Henüz hesabın yok mu?{" "}
          <Link href="/register" className="font-bold text-primary hover:underline">
            Kayıt ol
          </Link>
        </p>
      </form>
    </div>
  );
}
