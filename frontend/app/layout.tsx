import "./globals.css";

import type { Metadata } from "next";
import { Afacad, Commissioner } from "next/font/google";

import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/ui/sonner";

// WHY next/font: self-hosted font files, no FOIT/FOUT, and full Turkish support.
const afacad = Afacad({
  subsets: ["latin", "latin-ext"],
  variable: "--font-sans",
  display: "swap",
});

const commissioner = Commissioner({
  subsets: ["latin", "latin-ext"],
  variable: "--font-display",
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
      <body className={`${afacad.variable} ${commissioner.variable} font-sans`}>
        <ThemeProvider>
          {children}
          <Toaster />
        </ThemeProvider>
      </body>
    </html>
  );
}
