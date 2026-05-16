import { ReceiptHero } from "@/components/ReceiptHero";
import { ReceiptUploader } from "@/components/ReceiptUploader";

export const metadata = {
  title: "Fişler — Cüzdan Koçu",
};

export default function ReceiptsPage() {
  return (
    <div className="page-enter space-y-8">
      <ReceiptHero />

      <ReceiptUploader />
    </div>
  );
}
