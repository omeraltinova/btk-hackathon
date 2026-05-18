"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import * as React from "react";

/**
 * Wraps `next-themes` with project-wide defaults.
 * - `attribute="class"` → toggles `.dark` on <html>, matches Tailwind config.
 * - `defaultTheme="light"` → first visit opens with the intended warm ledger palette.
 */
export function ThemeProvider({
  children,
  ...props
}: React.ComponentProps<typeof NextThemesProvider>) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="light"
      enableSystem={false}
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  );
}
