import { redirect } from "next/navigation";

export const metadata = {
  title: "Zarf Detayı — Cüzdan Koçu",
};

type DashboardGoalEnvelopeDetailPageProps = {
  params: Promise<{ slug: string }>;
};

export default async function DashboardGoalEnvelopeDetailPage({
  params,
}: DashboardGoalEnvelopeDetailPageProps) {
  const { slug } = await params;
  redirect(`/dashboard/goals?zarf=${encodeURIComponent(slug)}`);
}
