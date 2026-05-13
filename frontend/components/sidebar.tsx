"use client";

import {
  BookOpen,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  PiggyBank,
  Receipt,
  Sparkles,
  Sticker,
  Target,
  UserRound,
  Users,
  Wallet,
  WalletCards,
} from "lucide-react";
import type { Session } from "next-auth";
import { signOut } from "next-auth/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { useKidMode } from "@/lib/kid-mode";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Panel", section: "01", icon: LayoutDashboard },
  { href: "/dashboard/transactions", label: "İşlemler", section: "02", icon: WalletCards },
  { href: "/dashboard/goals", label: "Hedefler", section: "03", icon: Target },
  { href: "/learn", label: "Dersler", section: "04", icon: BookOpen },
  { href: "/chat", label: "Sohbet", section: "05", icon: MessageSquare },
  { href: "/receipts", label: "Fişler", section: "06", icon: Receipt },
  { href: "/family", label: "Aile", section: "07", icon: Users },
  { href: "/account", label: "Hesap", section: "08", icon: UserRound },
] as const;

const KID_NAV_ITEMS = [
  { href: "/dashboard", label: "Cüzdanım", section: "01", icon: PiggyBank },
  { href: "/dashboard/transactions", label: "Hareketler", section: "02", icon: WalletCards },
  { href: "/dashboard/goals", label: "Hedefim", section: "03", icon: Target },
  { href: "/learn", label: "Öğren", section: "04", icon: BookOpen },
  { href: "/chat", label: "Koç", section: "05", icon: Sparkles },
  { href: "/receipts", label: "Fişlerim", section: "06", icon: Sticker },
  { href: "/account", label: "Profilim", section: "07", icon: UserRound },
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
  const { isKid } = useKidMode();
  const [isCollapsed, setIsCollapsed] = useState(false);
  const baseNavItems = isKid
    ? KID_NAV_ITEMS
    : user.role === "individual"
      ? NAV_ITEMS.filter((item) => item.href !== "/family")
      : NAV_ITEMS;
  const navItems = baseNavItems;
  const displayName = user.name ?? "Cüzdan Koçu";
  const brandTitle = isKid ? "Mini Cüzdan" : "Cüzdan Koçu";
  const brandSubtitle = isKid ? "Senin küçük cüzdanın" : "Ev bütçesi defteri";
  const roleChip = user.isDemo ? "Demo" : isKid ? "Çocuk modu" : ROLE_LABELS[user.role];

  useEffect(() => {
    setIsCollapsed(window.localStorage.getItem("cuzdan-kocu.sidebar") === "collapsed");
  }, []);

  function handleToggleSidebar() {
    setIsCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem("cuzdan-kocu.sidebar", next ? "collapsed" : "expanded");
      return next;
    });
  }

  return (
    <aside
      className={cn(
        "sticky top-0 z-40 flex w-full shrink-0 flex-col border-b border-border/80 bg-card/95 backdrop-blur-xl transition-[width] duration-300 ease-quint lg:h-screen lg:border-b-0 lg:border-r lg:bg-card",
        isCollapsed ? "lg:w-20" : "lg:w-72",
      )}
    >
      {/* Brand */}
      <div
        className={cn(
          "binder-holes relative flex items-center justify-between gap-3 px-3 py-3 sm:px-4 sm:py-4 lg:px-5 lg:py-6",
          isCollapsed ? "lg:flex-col" : "lg:block lg:px-8 lg:py-7",
        )}
      >
        <div className="flex min-w-0 items-center gap-3">
          <div className="hard-shadow-accent grid h-11 w-11 place-items-center rounded-[1rem_1rem_0.55rem_1rem] border border-primary/30 bg-primary text-primary-foreground">
            <Wallet className="h-5 w-5" />
          </div>
          <div className={cn("min-w-0", isCollapsed && "lg:hidden")}>
            <span className="block truncate font-display text-xl font-bold tracking-tight">
              {brandTitle}
            </span>
            <p className="text-xs text-muted-foreground">{brandSubtitle}</p>
          </div>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="hidden rounded-[1rem] lg:inline-flex"
          aria-label={isCollapsed ? "Sol menüyü genişlet" : "Sol menüyü daralt"}
          title={isCollapsed ? "Sol menüyü genişlet" : "Sol menüyü daralt"}
          onClick={handleToggleSidebar}
        >
          {isCollapsed ? (
            <PanelLeftOpen className="h-4 w-4" />
          ) : (
            <PanelLeftClose className="h-4 w-4" />
          )}
        </Button>
        <span
          className={cn(
            "stamp-label shrink-0 bg-background/65 text-primary lg:mt-6 lg:inline-flex",
            isCollapsed && "lg:hidden",
          )}
        >
          {roleChip}
        </span>
      </div>

      <div
        className={cn(
          "mx-4 hidden rotate-[-1deg] items-center gap-3 rounded-[1.4rem_1.4rem_0.8rem_1.4rem] border border-border/80 bg-muted/70 px-3 py-3 lg:flex",
          isCollapsed && "lg:hidden",
        )}
      >
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
              title={item.label}
              className={cn(
                "tab-chip flex min-h-11 shrink-0 items-center gap-2 px-3 py-2.5 pr-5 text-sm font-bold transition-all duration-200 ease-quint sm:gap-3 sm:px-4 sm:pr-6 lg:w-full",
                isCollapsed && "lg:justify-center lg:px-3 lg:pr-3",
                isActive
                  ? "hard-shadow-accent bg-primary text-primary-foreground"
                  : "bg-muted/45 text-muted-foreground hover:bg-accent/45 hover:text-accent-foreground motion-safe:hover:-translate-y-0.5",
              )}
            >
              <span className={cn("font-display text-xs opacity-70", isCollapsed && "lg:hidden")}>
                {item.section}
              </span>
              <Icon className="h-4 w-4" />
              <span className={cn(isCollapsed && "lg:hidden")}>{item.label}</span>
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
          className={cn(
            "w-full rounded-[1.1rem] text-muted-foreground",
            isCollapsed ? "justify-center px-0" : "justify-start",
          )}
          title="Çıkış"
          onClick={() => void signOut({ callbackUrl: "/login" })}
        >
          <LogOut className="h-4 w-4" />
          <span className={cn(isCollapsed && "lg:hidden")}>Çıkış</span>
        </Button>
      </div>
    </aside>
  );
}
