import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata = {
  title: "Panel — Cüzdan Koçu",
};

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight">Panel</h1>
        <p className="text-muted-foreground">
          Bu ayki harcama özetin, son işlemlerin ve proaktif uyarıların burada görünür.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Yakında</CardTitle>
          <CardDescription>
            Day 3'te canlanacak: özet kartlar, harcama grafiği ve son işlemler listesi.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Veri akışı <code className="rounded bg-muted px-1 py-0.5">/api/transactions</code> ve{" "}
          <code className="rounded bg-muted px-1 py-0.5">/api/insights</code> üzerinden gelecek.
        </CardContent>
      </Card>
    </div>
  );
}
