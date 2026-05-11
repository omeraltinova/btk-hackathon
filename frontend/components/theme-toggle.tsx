"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import * as React from "react";

import { Button } from "@/components/ui/button";

/**
 * Single-button theme toggle. Cycles light → dark → system.
 * WHY a 3-state cycle (not just light/dark): respects users who prefer to
 * inherit from the OS, which is the master_plan default.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  // Avoid hydration mismatch — `theme` is undefined on the server.
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const next = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";
  const label =
    theme === "light"
      ? "Tema: açık (karanlığa geç)"
      : theme === "dark"
        ? "Tema: koyu (sisteme geç)"
        : "Tema: sistem (açığa geç)";

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={label}
      title={label}
      onClick={() => setTheme(next)}
    >
      {/* Icons only render after mount to avoid mismatched SSR markup. */}
      {mounted ? (
        theme === "dark" ? (
          <Moon className="h-4 w-4" />
        ) : (
          <Sun className="h-4 w-4" />
        )
      ) : (
        <Sun className="h-4 w-4 opacity-0" />
      )}
    </Button>
  );
}
