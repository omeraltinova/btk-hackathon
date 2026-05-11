import { ThemeToggle } from "@/components/theme-toggle";
import { Sidebar } from "@/components/sidebar";

/**
 * Shell layout for authenticated app pages.
 *
 * Why a route group `(app)`: the `/login` route lives under `(auth)` and must
 * NOT render the sidebar. Route groups let us share a layout for all
 * dashboard-like routes without leaking it into `/login`.
 *
 * Day 1: no auth gate. Day 2 will add a server-side auth check here that
 * redirects unauthenticated visitors to `/login`.
 */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen lg:flex">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="bg-background/82 flex min-h-16 items-center justify-between gap-4 border-b border-border/70 px-4 py-3 backdrop-blur sm:px-6 lg:px-8">
          <div className="hidden min-w-0 sm:block">
            <p className="eyebrow">11.05.2026 / defter açık</p>
            <p className="truncate text-sm text-muted-foreground">
              Proaktif uyarılar, aile görünümü ve fiş akışı hazırlandığında burada birleşecek.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground sm:ml-auto">
            <span className="stamp-label hidden bg-card/70 text-muted-foreground sm:inline-flex">
              1. gün tasarım modu
            </span>
          </div>
          <ThemeToggle />
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-5 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
