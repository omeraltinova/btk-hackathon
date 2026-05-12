import { DashboardClient } from "@/components/dashboard-client";

export const metadata = {
  title: "Tekrarlayan Ödemeler — Cüzdan Koçu",
};

export default function DashboardRecurringPage() {
  return <DashboardClient view="recurring" />;
}
