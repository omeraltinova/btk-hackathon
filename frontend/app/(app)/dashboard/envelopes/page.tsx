import { redirect } from "next/navigation";

export const metadata = {
  title: "Zarf Bütçesi — Cüzdan Koçu",
};

export default function DashboardEnvelopesPage() {
  redirect("/dashboard/goals?sekme=zarflar");
}
