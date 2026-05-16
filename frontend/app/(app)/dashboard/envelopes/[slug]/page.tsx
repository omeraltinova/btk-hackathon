import { redirect } from "next/navigation";

export const metadata = {
  title: "Zarf Detayı — Cüzdan Koçu",
};

type DashboardEnvelopeDetailPageProps = {
  params: Promise<{ slug: string }>;
};

export default async function DashboardEnvelopeDetailPage({
  params,
}: DashboardEnvelopeDetailPageProps) {
  const { slug } = await params;
  redirect(`/dashboard/goals?zarf=${encodeURIComponent(slug)}`);
}
