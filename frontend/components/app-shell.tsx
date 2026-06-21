"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Menu, X } from "lucide-react";
import { api } from "@/lib/api";
import { ThemeToggle } from "@/components/theme-toggle";

const GROUPS: { title: string; items: { href: string; label: string }[] }[] = [
  {
    title: "Resumen",
    items: [
      { href: "/", label: "Dashboard" },
      { href: "/reports", label: "Reportes" },
    ],
  },
  {
    title: "Movimiento",
    items: [
      { href: "/transactions", label: "Transacciones" },
      { href: "/to-pay", label: "Por pagar" },
      { href: "/recurring", label: "Recurrentes" },
    ],
  },
  {
    title: "Planeación",
    items: [
      { href: "/goals", label: "Metas" },
      { href: "/budgets", label: "Presupuestos" },
    ],
  },
  {
    title: "Configuración",
    items: [
      { href: "/accounts", label: "Cuentas" },
      { href: "/categories", label: "Categorías" },
      { href: "/category-groups", label: "Grupos" },
      { href: "/tags", label: "Etiquetas" },
      { href: "/settings", label: "Ajustes" },
    ],
  },
];

function NavLinks({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav className="space-y-5">
      {GROUPS.map((g) => (
        <div key={g.title} className="space-y-1">
          <p className="px-2 text-[0.7rem] font-medium uppercase tracking-wider" style={{ color: "var(--muted-foreground)" }}>
            {g.title}
          </p>
          {g.items.map((n) => {
            const active = pathname === n.href;
            return (
              <Link
                key={n.href}
                href={n.href}
                onClick={onNavigate}
                className="block rounded-md px-2 py-1.5 text-sm transition-colors"
                style={{
                  color: active ? "var(--foreground)" : "var(--muted-foreground)",
                  fontWeight: active ? 500 : 400,
                  background: active
                    ? "color-mix(in oklch, var(--primary) 14%, transparent)"
                    : "transparent",
                }}
              >
                {n.label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const qc = useQueryClient();
  const [drawer, setDrawer] = useState(false);

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
    <div className="flex min-h-screen">
      {/* Desktop sidebar */}
      <aside
        className="sticky top-0 hidden h-screen w-56 shrink-0 flex-col justify-between border-r p-4 md:flex"
        style={{ background: "var(--sidebar)", borderColor: "var(--sidebar-border)" }}
      >
        <div className="space-y-6">
          <Link href="/" className="font-display block px-2 text-base font-semibold tracking-tight">
            Quaestor
          </Link>
          <NavLinks pathname={pathname} />
        </div>
        <div className="flex items-center justify-between px-2">
          <button onClick={logout} className="text-left text-sm transition-colors hover:text-[var(--foreground)]" style={{ color: "var(--muted-foreground)" }}>
            Salir
          </button>
          <ThemeToggle />
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-12 items-center gap-3 border-b px-4 md:hidden" style={{ background: "var(--card)", borderColor: "var(--border)" }}>
          <button onClick={() => setDrawer(true)} aria-label="Abrir menú">
            <Menu className="size-5" />
          </button>
          <span className="font-display text-base font-semibold tracking-tight">Quaestor</span>
          <ThemeToggle className="ml-auto" />
        </header>

        {/* Mobile drawer */}
        {drawer && (
          <div className="fixed inset-0 z-50 md:hidden">
            <div className="absolute inset-0 bg-black/40" onClick={() => setDrawer(false)} />
            <aside
              className="absolute left-0 top-0 flex h-full w-64 flex-col justify-between p-4"
              style={{ background: "var(--sidebar)" }}
            >
              <div className="space-y-6">
                <div className="flex items-center justify-between px-2">
                  <span className="font-display text-base font-semibold tracking-tight">Quaestor</span>
                  <button onClick={() => setDrawer(false)} aria-label="Cerrar menú">
                    <X className="size-5" />
                  </button>
                </div>
                <NavLinks pathname={pathname} onNavigate={() => setDrawer(false)} />
              </div>
              <button onClick={logout} className="px-2 text-left text-sm" style={{ color: "var(--muted-foreground)" }}>
                Salir
              </button>
            </aside>
          </div>
        )}

        <main className="mx-auto w-full max-w-5xl flex-1 px-5 py-8">{children}</main>
      </div>
    </div>
  );
}
