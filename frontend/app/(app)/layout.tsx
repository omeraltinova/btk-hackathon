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
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col">
        <header className="flex h-14 items-center justify-end gap-2 border-b px-6">
          <ThemeToggle />
        </header>
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
