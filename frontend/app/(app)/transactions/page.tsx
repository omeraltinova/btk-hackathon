import { DashboardClient } from "@/components/dashboard-client";

export const metadata = {
  title: "İşlemler — Cüzdan Koçu",
};

export default function TransactionsPage() {
  return <DashboardClient view="transactions" />;
}
