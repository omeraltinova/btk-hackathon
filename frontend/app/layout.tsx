import "./globals.css";

import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";

// WHY Inter via next/font: zero-config self-hosting, no FOIT/FOUT, fully
// supports Turkish characters (Latin Extended).
const inter = Inter({
  subsets: ["latin", "latin-ext"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Cüzdan Koçu — Türk aileleri için finans koçu",
  description:
    "Cüzdan Koçu, Türk aileleri için harcamalarını yöneten ve finansal okuryazarlığı öğreten proaktif bir AI ajanıdır.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    // suppressHydrationWarning is required by next-themes — the `class`
    // attribute differs server vs. client until the theme mounts.
    <html lang="tr" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans`}>
        <ThemeProvider>
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
