import { redirect } from "next/navigation"
import { AppShell } from "@/components/app-shell"
import { isAuthenticated } from "@/lib/server-auth"

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  if (!(await isAuthenticated())) redirect("/login")
  return <AppShell>{children}</AppShell>
}
