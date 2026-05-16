import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { ActiveProfileBanner } from "@/components/ActiveProfileBanner";
import { ThemeToggle } from "@/components/theme-toggle";
import { Sidebar } from "@/components/sidebar";
import { authOptions } from "@/lib/auth";
import { KidModeProvider } from "@/lib/kid-mode";

/**
 * Shell layout for authenticated app pages.
 *
 * Why a route group `(app)`: the `/login` route lives under `(auth)` and must
 * NOT render the sidebar. Route groups let us share a layout for all
 * dashboard-like routes without leaking it into `/login`.
 *
 */
export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await getServerSession(authOptions);
  if (!session?.backendToken) redirect("/login");

  return (
    <KidModeProvider>
      <div className="min-h-screen lg:flex">
        <Sidebar user={session.user} />
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="bg-background/88 flex min-h-16 items-center justify-end border-b border-border/70 px-3 py-3 backdrop-blur sm:px-6 lg:px-8">
            <div className="flex min-w-0 items-center justify-end gap-2 text-xs text-muted-foreground">
              <ActiveProfileBanner />
              <ThemeToggle />
            </div>
          </header>
          <main className="w-full min-w-0 flex-1 overflow-x-hidden px-3 py-5 sm:px-6 lg:px-8 lg:py-8 2xl:px-10">
            {children}
          </main>
        </div>
      </div>
    </KidModeProvider>
  );
}
