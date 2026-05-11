"use client";

import { LayoutDashboard, LogOut, MessageSquare, Receipt, Users, Wallet } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// HARDCODED_DEMO_USER — Day 1 stand-in until auth context lands Day 2.
// TODO Day 2: replace with auth context (NextAuth session → user object).
const HARDCODED_DEMO_USER = {
  name: "Ayşe Yılmaz",
  family: "Yılmaz",
  role: "parent" as const,
  email: "ayse@demo.cuzdan-kocu.app",
};

const NAV_ITEMS = [
  { href: "/dashboard", label: "Panel", icon: LayoutDashboard },
  { href: "/chat", label: "Sohbet", icon: MessageSquare },
  { href: "/receipts", label: "Fişler", icon: Receipt },
  { href: "/family", label: "Aile", icon: Users },
] as const;

function initials(name: string): string {
  return name
    .split(" ")
    .map((n) => n[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r bg-card">
      {/* Brand */}
      <div className="flex items-center gap-2 px-6 py-6">
        <Wallet className="h-6 w-6 text-primary" />
        <span className="text-lg font-semibold tracking-tight">Cüzdan Koçu</span>
      </div>

      {/* User chip (Day 1: hard-coded demo user) */}
      <div className="mx-3 flex items-center gap-3 rounded-lg bg-muted px-3 py-3">
        <Avatar className="h-9 w-9">
          <AvatarFallback>{initials(HARDCODED_DEMO_USER.name)}</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-medium">{HARDCODED_DEMO_USER.name}</div>
          <div className="truncate text-xs text-muted-foreground">
            Aile: {HARDCODED_DEMO_USER.family}
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="mt-4 flex-1 space-y-1 px-3">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Logout (Day 1: stub — wired Day 2) */}
      <div className="border-t p-3">
        <Button
          variant="ghost"
          className="w-full justify-start text-muted-foreground"
          // TODO Day 2: clear JWT + redirect to /login.
          disabled
        >
          <LogOut className="h-4 w-4" />
          Çıkış
        </Button>
      </div>
    </aside>
  );
}
