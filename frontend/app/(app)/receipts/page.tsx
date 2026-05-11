import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata = {
  title: "Fişler — Cüzdan Koçu",
};

export default function ReceiptsPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight">Fişler</h1>
        <p className="text-muted-foreground">
          Fişini sürükle bırak; Cüzdan Koçu kalemleri çıkarır, kategorisini önerir, onayınla işleme
          ekler.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Yakında</CardTitle>
          <CardDescription>
            Day 4'te canlanacak: drag-drop yükleyici, OCR önizleme, onay akışı.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Yükleme <code className="rounded bg-muted px-1 py-0.5">/api/receipts/upload</code>'a; OCR
          Gemini 2.5 Vision ile yapılır.
        </CardContent>
      </Card>
    </div>
  );
}
