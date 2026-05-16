import { redirect } from "next/navigation";

export const metadata = {
  title: "İşlemler — Cüzdan Koçu",
};

export default function ReceiptsPage() {
  redirect("/dashboard/transactions");
}
