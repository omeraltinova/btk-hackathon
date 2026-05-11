import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata = {
  title: "Aile — Cüzdan Koçu",
};

export default function FamilyPage() {
  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold tracking-tight">Aile</h1>
        <p className="text-muted-foreground">
          Çocuklarını ekle, profilleri arasında geçiş yap, harçlık ve hedef takibini bir arada gör.
        </p>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Yakında</CardTitle>
          <CardDescription>
            Day 5'te canlanacak: aile listesi, çocuk ekle akışı, family switch.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          Bu sayfa sadece <span className="font-medium">parent</span> rolündeki kullanıcılara
          görünür. Child kullanıcılarda gizlenecek (master_plan §8 İK-4, İK-5).
        </CardContent>
      </Card>
    </div>
  );
}
