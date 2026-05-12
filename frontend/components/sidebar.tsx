"use client";

import {
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Receipt,
  Repeat2,
  Users,
  Wallet,
  WalletCards,
} from "lucide-react";
import type { Session } from "next-auth";
import { signOut } from "next-auth/react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Panel", section: "01", icon: LayoutDashboard },
  { href: "/dashboard/transactions", label: "İşlemler", section: "02", icon: WalletCards },
  { href: "/dashboard/recurring", label: "Tekrarlar", section: "03", icon: Repeat2 },
  { href: "/chat", label: "Sohbet", section: "04", icon: MessageSquare },
  { href: "/receipts", label: "Fişler", section: "05", icon: Receipt },
  { href: "/family", label: "Aile", section: "06", icon: Users },
] as const;

const ROLE_LABELS = {
  parent: "Ebeveyn",
  child: "Çocuk",
  individual: "Bireysel",
} as const;

function initials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

type SidebarProps = {
  user: Session["user"];
};

export function Sidebar({ user }: SidebarProps) {
  const pathname = usePathname();
  const navItems =
    user.role === "individual" ? NAV_ITEMS.filter((item) => item.href !== "/family") : NAV_ITEMS;
  const displayName = user.name ?? "Cüzdan Koçu";

  return (
    <aside className="sticky top-0 z-40 flex w-full shrink-0 flex-col border-b border-border/80 bg-card/95 backdrop-blur-xl lg:h-screen lg:w-72 lg:border-b-0 lg:border-r lg:bg-card">
      {/* Brand */}
      <div className="binder-holes relative flex items-center justify-between gap-3 px-3 py-3 sm:px-4 sm:py-4 lg:block lg:px-8 lg:py-7">
        <div className="flex min-w-0 items-center gap-3">
          <div className="hard-shadow-accent grid h-11 w-11 place-items-center rounded-[1rem_1rem_0.55rem_1rem] border border-primary/30 bg-primary text-primary-foreground">
            <Wallet className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <span className="block truncate font-display text-xl font-bold tracking-tight">
              Cüzdan Koçu
            </span>
            <p className="text-xs text-muted-foreground">Ev bütçesi defteri</p>
          </div>
        </div>
        <span className="stamp-label shrink-0 bg-background/65 text-primary lg:mt-6 lg:inline-flex">
          {user.isDemo ? "Demo" : ROLE_LABELS[user.role]}
        </span>
      </div>

      <div className="mx-4 hidden rotate-[-1deg] items-center gap-3 rounded-[1.4rem_1.4rem_0.8rem_1.4rem] border border-border/80 bg-muted/70 px-3 py-3 lg:flex">
        <Avatar className="h-9 w-9">
          <AvatarFallback>{initials(displayName)}</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{displayName}</div>
          <div className="truncate text-xs text-muted-foreground">{ROLE_LABELS[user.role]}</div>
        </div>
      </div>

      {/* Nav */}
      <nav
        aria-label="Ana menü"
        className="flex gap-2 overflow-x-auto px-3 pb-3 [scrollbar-width:none] lg:mt-6 lg:flex-1 lg:flex-col lg:gap-2 lg:overflow-visible lg:px-4 lg:pb-0 [&::-webkit-scrollbar]:hidden"
      >
        {navItems.map((item) => {
          const isActive =
            item.href === "/dashboard"
              ? pathname === item.href
              : pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "tab-chip flex min-h-11 shrink-0 items-center gap-2 px-3 py-2.5 pr-5 text-sm font-bold transition-all duration-200 ease-quint sm:gap-3 sm:px-4 sm:pr-6 lg:w-full",
                isActive
                  ? "hard-shadow-accent bg-primary text-primary-foreground"
                  : "bg-muted/45 text-muted-foreground hover:bg-accent/45 hover:text-accent-foreground motion-safe:hover:-translate-y-0.5",
              )}
            >
              <span className="font-display text-xs opacity-70">{item.section}</span>
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
        <button
          type="button"
          className="tab-chip flex min-h-11 shrink-0 items-center gap-2 bg-muted/45 px-3 py-2.5 pr-5 text-sm font-bold text-muted-foreground transition-all duration-200 ease-quint hover:bg-accent/45 hover:text-accent-foreground sm:gap-3 sm:px-4 sm:pr-6 lg:hidden"
          onClick={() => void signOut({ callbackUrl: "/login" })}
        >
          <LogOut className="h-4 w-4" />
          Çıkış
        </button>
      </nav>

      <div className="hidden border-t border-border/70 p-4 lg:block">
        <Button
          variant="ghost"
          className="w-full justify-start rounded-[1.1rem] text-muted-foreground"
          onClick={() => void signOut({ callbackUrl: "/login" })}
        >
          <LogOut className="h-4 w-4" />
          Çıkış
        </Button>
      </div>
    </aside>
  );
}
