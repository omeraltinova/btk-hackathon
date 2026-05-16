import { redirect } from "next/navigation";

export const metadata = {
  title: "Hedef Detayı — Cüzdan Koçu",
};

type DashboardGoalDetailPageProps = {
  params: Promise<{ goalId: string }>;
};

export default async function DashboardGoalDetailPage({ params }: DashboardGoalDetailPageProps) {
  const { goalId } = await params;
  redirect(`/dashboard/goals?hedef=${encodeURIComponent(goalId)}`);
}
