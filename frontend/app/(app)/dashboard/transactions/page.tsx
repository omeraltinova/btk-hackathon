import { DashboardClient } from "@/components/dashboard-client";

export const metadata = {
  title: "İşlemler — Cüzdan Koçu",
};

export default function DashboardTransactionsPage() {
  return <DashboardClient view="transactions" />;
}
