import { Wallet } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export const metadata = {
  title: "Giriş — Cüzdan Koçu",
};

/**
 * Day 1 placeholder.
 *
 * The form is shown for layout review only — it does NOT submit anywhere yet.
 * Day 2 will wire the submit handler to `/api/auth/login` and store the JWT
 * via `lib/api.ts` setToken(), then redirect to /dashboard.
 *
 * Design note: master_plan §12.1 specifies email + password (bcrypt).
 * Magic link is in §12.3 stretch and is NOT built unless we have time after Day 7.
 */
export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="space-y-2 text-center">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-full bg-primary/10">
            <Wallet className="h-5 w-5 text-primary" />
          </div>
          <CardTitle>Cüzdan Koçu'na giriş</CardTitle>
          <CardDescription>E-posta adresin ve şifrenle giriş yap.</CardDescription>
        </CardHeader>
        <CardContent>
          {/* Day 2: convert to client component, wire onSubmit to /api/auth/login.
              Inputs are individually `disabled` for now; that's the a11y-correct
              way to indicate the form isn't yet operational. */}
          <form className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="email" className="text-sm font-medium">
                E-posta
              </label>
              <Input
                id="email"
                type="email"
                placeholder="ornek@cuzdan-kocu.app"
                autoComplete="email"
                disabled
              />
            </div>
            <div className="space-y-2">
              <label htmlFor="password" className="text-sm font-medium">
                Şifre
              </label>
              <Input id="password" type="password" autoComplete="current-password" disabled />
            </div>
            <Button type="button" className="w-full" disabled>
              Giriş yap (Day 2)
            </Button>
          </form>
          <p className="mt-6 text-center text-xs text-muted-foreground">
            Henüz hesabın yok mu? Kayıt akışı Day 2'de aktifleşir.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
