"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/reports", label: "Reportes" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const qc = useQueryClient();

  async function logout() {
    try {
      await api.logout();
    } finally {
      qc.clear();
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b bg-white">
        <nav className="mx-auto flex h-12 max-w-5xl items-center gap-7 px-5">
          <Link href="/" className="text-sm font-semibold tracking-tight text-foreground">
            Quaestor
          </Link>

          <div className="flex items-center gap-1">
            {NAV.map((n) => {
              const active = pathname === n.href;
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className="px-2.5 py-1 text-sm rounded transition-colors"
                  style={{
                    color: active ? "var(--foreground)" : "var(--muted-foreground)",
                    fontWeight: active ? 500 : 400,
                    background: active ? "var(--muted)" : "transparent",
                  }}
                >
                  {n.label}
                </Link>
              );
            })}
          </div>

          <button
            onClick={logout}
            className="ml-auto text-sm transition-colors"
            style={{ color: "var(--muted-foreground)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--foreground)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--muted-foreground)")}
          >
            Salir
          </button>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-5 py-8">{children}</main>
    </div>
  );
}
