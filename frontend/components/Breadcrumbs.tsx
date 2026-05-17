"use client";

import { ChevronRight, Home } from "lucide-react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

import { cn } from "@/lib/utils";

type Crumb = {
  label: string;
  href?: string;
};

const PATH_LABELS: Record<string, string> = {
  "/dashboard": "Panel",
  "/transactions": "İşlemler",
  "/income-expense": "Gelir/Gider",
  "/goals": "Hedefler",
  "/learn": "Dersler",
  "/chat": "Sohbet",
  "/chat/history": "Sohbet geçmişi",
  "/family": "Aile",
  "/account": "Hesap",
  "/account/memory": "Hafıza",
};

// Map well-known envelope slugs back to a Turkish display name; falls back to
// title-casing the slug for anything not in this table.
const ENVELOPE_LABELS: Record<string, string> = {
  market: "Market",
  fatura: "Fatura",
  okul: "Okul",
  egitim: "Eğitim",
  ulasim: "Ulaşım",
  ulaşım: "Ulaşım",
  harclik: "Harçlık",
  harçlık: "Harçlık",
  birikim: "Birikim",
};

function titleCase(slug: string): string {
  return slug
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map((token) => token.charAt(0).toLocaleUpperCase("tr-TR") + token.slice(1))
    .join(" ");
}

function deriveCrumbs(pathname: string, searchParams: URLSearchParams | null): Crumb[] {
  // Skip auth/system routes — no breadcrumb on those.
  if (pathname === "/" || pathname.startsWith("/login") || pathname.startsWith("/register")) {
    return [];
  }

  const crumbs: Crumb[] = [];
  const segments = pathname.split("/").filter(Boolean);

  let accumulated = "";
  for (const segment of segments) {
    accumulated += `/${segment}`;
    const label =
      PATH_LABELS[accumulated] ??
      (segment.length === 36 && segment.includes("-") ? null : titleCase(segment));
    if (label !== null) {
      crumbs.push({ label, href: accumulated });
    }
  }

  // Special-case `/goals?sekme=zarflar[&zarf=<slug>]` so the envelope view feels
  // like a nested page instead of a query-string toggle.
  if (pathname === "/goals" && searchParams !== null) {
    const sekme = searchParams.get("sekme");
    const zarf = searchParams.get("zarf");
    if (sekme === "zarflar" || zarf !== null) {
      crumbs.push({ label: "Zarflar", href: "/goals?sekme=zarflar" });
      if (zarf) {
        const labelKey = zarf.toLocaleLowerCase("tr-TR");
        crumbs.push({ label: ENVELOPE_LABELS[labelKey] ?? titleCase(zarf) });
      }
    }
  }

  // Strip the link on the last crumb — it's the current page.
  const last = crumbs[crumbs.length - 1];
  if (last !== undefined) {
    crumbs[crumbs.length - 1] = { label: last.label };
  }
  return crumbs;
}

export function Breadcrumbs() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const crumbs = deriveCrumbs(pathname, searchParams);

  if (crumbs.length === 0) return null;

  return (
    <nav
      aria-label="Sayfa konumu"
      className="hidden min-w-0 items-center gap-1 truncate text-xs font-semibold text-muted-foreground sm:flex"
    >
      <Link
        href="/dashboard"
        className="inline-flex items-center gap-1 rounded-full px-2 py-1 transition-colors hover:bg-muted/55 hover:text-foreground"
        aria-label="Panele dön"
      >
        <Home className="h-3.5 w-3.5" />
      </Link>
      {crumbs.map((crumb, index) => {
        const isLast = index === crumbs.length - 1;
        return (
          <span key={`${crumb.label}-${index}`} className="inline-flex items-center gap-1">
            <ChevronRight className="h-3.5 w-3.5 shrink-0 opacity-60" />
            {crumb.href !== undefined && !isLast ? (
              <Link
                href={crumb.href}
                className="rounded-full px-2 py-1 transition-colors hover:bg-muted/55 hover:text-foreground"
              >
                {crumb.label}
              </Link>
            ) : (
              <span
                aria-current={isLast ? "page" : undefined}
                className={cn(
                  "rounded-full px-2 py-1",
                  isLast ? "bg-muted/45 text-foreground" : undefined,
                )}
              >
                {crumb.label}
              </span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
