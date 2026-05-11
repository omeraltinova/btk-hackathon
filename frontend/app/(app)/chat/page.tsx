import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata = {
  title: "Sohbet — Cüzdan Koçu",
};

export default function ChatPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight">Sohbet</h1>
        <p className="text-muted-foreground">
          Cüzdan Koçu'na sor: harcamalar, abonelikler, finansal kavramlar veya senaryo simülasyonu.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Yakında</CardTitle>
          <CardDescription>
            Day 2'de streaming chat UI iskeleti; Day 3'te agent'a bağlanır.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Mesajlar <code className="rounded bg-muted px-1 py-0.5">/api/chat/stream</code> üzerinden
          akacak; agent state'inden tool çağrıları gerçek zamanlı görünür.
        </CardContent>
      </Card>
    </div>
  );
}
