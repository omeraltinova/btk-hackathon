import { redirect } from "next/navigation";

// Root URL → dashboard. Day 2 will make this redirect through the auth gate
// (unauthenticated users → /login, authenticated → /dashboard).
export default function Home() {
  redirect("/dashboard");
}
