"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import * as React from "react";

/**
 * Wraps `next-themes` with project-wide defaults.
 * - `attribute="class"` → toggles `.dark` on <html>, matches Tailwind config.
 * - `defaultTheme="system"` → respects OS preference per master_plan §5 P9 (user choice first).
 * - `enableSystem` → system change is reflected when no explicit choice is set.
 */
export function ThemeProvider({
  children,
  ...props
}: React.ComponentProps<typeof NextThemesProvider>) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
