"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import * as React from "react";

import { Button } from "@/components/ui/button";

/**
 * Single-button theme toggle.
 */
export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();

  // Avoid hydration mismatch — `theme` is undefined on the server.
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);

  const isDark = resolvedTheme === "dark";
  const next = isDark ? "light" : "dark";
  const label = isDark ? "Tema: koyu (açığa geç)" : "Tema: açık (karanlığa geç)";

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={label}
      title={label}
      onClick={() => setTheme(next)}
      disabled={!mounted}
    >
      {/* Icons only render after mount to avoid mismatched SSR markup. */}
      {mounted ? (
        isDark ? (
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
