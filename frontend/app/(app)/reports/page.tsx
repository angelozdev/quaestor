"use client"

import { useQuery } from "@tanstack/react-query"
import { format } from "date-fns"
import { useState } from "react"
import { EmptyState } from "@/components/empty-state"
import { MoneyAmount } from "@/components/money-amount"
import { PageHeader } from "@/components/page-header"
import { QueryBoundary } from "@/components/query-boundary"
import { SkeletonCard } from "@/components/skeleton"
import { report } from "@/lib/api/reports"
import { nounOf, shapeOf } from "@/lib/funds"
import { formatCents } from "@/lib/money"
import { qk } from "@/lib/query"

const CARD_STYLE = {
  background: "var(--card)",
  boxShadow: "var(--shadow-card)",
  borderRadius: "var(--radius)",
} as const

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium" style={{ color: "var(--muted-foreground)" }}>
        {title}
      </h2>
      <div className="p-5" style={CARD_STYLE}>
        {children}
      </div>
    </div>
  )
}

function Row({
  label,
  children,
  faint = false,
}: {
  label: string
  children: React.ReactNode
  faint?: boolean
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span
        className="text-sm"
        style={{ color: faint ? "var(--muted-foreground)" : "var(--foreground)" }}
      >
        {label}
      </span>
      {children}
    </div>
  )
}

export default function ReportsPage() {
  const [month, setMonth] = useState(format(new Date(), "yyyy-MM"))
  const q = useQuery({
    queryKey: qk.report(month),
    queryFn: () => report(month),
  })

  return (
    <div className="space-y-8">
      <PageHeader
        title="Reportes"
        subtitle={month}
        action={
          <input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="rounded-md px-3 py-1.5 text-sm outline-none transition-colors w-40"
            style={{
              background: "var(--input)",
              border: "1px solid var(--border)",
              color: "var(--foreground)",
              colorScheme: "light",
            }}
            onFocus={(e) => (e.target.style.borderColor = "var(--foreground)")}
            onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
          />
        }
      />

      <QueryBoundary
        query={q}
        skeleton={
          <div className="space-y-3">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        }
        errorMessage="No se pudo cargar el reporte"
      >
        {(data) => (
          <div className="space-y-6 animate-fade-up">
            {/* Neto */}
            <Section title="Resultado del mes">
              <div className="space-y-4">
                <div className="space-y-0.5">
                  <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                    Neto
                  </p>
                  <p
                    className="text-4xl font-bold tabular-nums tracking-tight"
                    style={{ color: data.net >= 0 ? "var(--income)" : "var(--expense)" }}
                  >
                    {formatCents(data.net, "COP")}
                  </p>
                </div>
                <hr style={{ borderColor: "var(--border)" }} />
                <div className="space-y-1">
                  <Row label="Ingresos">
                    <MoneyAmount
                      cents={data.income}
                      currency="COP"
                      type="income"
                      className="text-sm font-medium"
                    />
                  </Row>
                  <Row label="Gastos" faint>
                    <MoneyAmount
                      cents={data.expense}
                      currency="COP"
                      type="expense"
                      className="text-sm font-medium"
                    />
                  </Row>
                </div>
                {data.drift_mom && (
                  <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                    vs {data.drift_mom.prev_month} →{" "}
                    <span
                      style={{
                        color: data.drift_mom.net_abs >= 0 ? "var(--income)" : "var(--expense)",
                      }}
                    >
                      {data.drift_mom.net_abs >= 0 ? "+" : ""}
                      {formatCents(data.drift_mom.net_abs, "COP")}
                    </span>
                  </p>
                )}
              </div>
            </Section>

            <Section title="Fondos y presupuestos">
              {data.funds.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr style={{ color: "var(--muted-foreground)" }}>
                      <th className="text-left pb-3 font-medium text-xs">Categoría</th>
                      <th className="text-right pb-3 font-medium text-xs">Pidió</th>
                      <th className="text-right pb-3 font-medium text-xs">Gastado</th>
                      <th className="text-right pb-3 font-medium text-xs">Tiene</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.funds.map((f) => (
                      <tr
                        key={f.category_name}
                        className="border-t"
                        style={{ borderColor: "var(--border)" }}
                      >
                        <td className="py-2.5 text-sm">{f.category_name}</td>
                        <td
                          className="py-2.5 text-right tabular-nums text-sm"
                          style={{ color: "var(--muted-foreground)" }}
                        >
                          {formatCents(f.asks, "COP")}
                        </td>
                        <td
                          className="py-2.5 text-right tabular-nums text-sm"
                          style={{ color: "var(--muted-foreground)" }}
                        >
                          {formatCents(f.spent, "COP")}
                        </td>
                        <td
                          className="py-2.5 text-right tabular-nums text-sm font-medium"
                          style={{ color: f.on_track ? "var(--income)" : "var(--expense)" }}
                        >
                          {formatCents(f.holds, "COP")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <EmptyState
                  message="Sin fondos este mes"
                  action={{ label: "Ir a fondos", href: "/funds" }}
                />
              )}
            </Section>

            {/* Por categoría */}
            <Section title="Por categoría">
              {data.by_category.length > 0 ? (
                <div className="space-y-1">
                  {data.by_category.map((c) => (
                    <Row key={c.category} label={c.category} faint>
                      <div className="flex items-baseline gap-3 shrink-0">
                        <span className="text-sm font-medium tabular-nums">
                          {formatCents(c.total, "COP")}
                        </span>
                        <span
                          className="text-xs w-9 text-right"
                          style={{ color: "var(--muted-foreground)" }}
                        >
                          {c.pct.toFixed(1)}%
                        </span>
                      </div>
                    </Row>
                  ))}
                </div>
              ) : (
                <EmptyState message="Sin gastos este mes" />
              )}
            </Section>

            {/* Por grupo */}
            <Section title="Por grupo">
              {data.by_group.length > 0 ? (
                <div className="space-y-1">
                  {data.by_group.map((g) => (
                    <Row key={g.group} label={g.group} faint>
                      <div className="flex items-baseline gap-3 shrink-0">
                        <span className="text-sm font-medium tabular-nums">
                          {formatCents(g.total, "COP")}
                        </span>
                        <span
                          className="text-xs w-9 text-right"
                          style={{ color: "var(--muted-foreground)" }}
                        >
                          {g.pct.toFixed(1)}%
                        </span>
                      </div>
                    </Row>
                  ))}
                </div>
              ) : (
                <EmptyState message="Sin gastos agrupados este mes" />
              )}
            </Section>

            {/* Cierre */}
            <Section title="Disponible · cierre">
              <div className="space-y-4">
                <p className="text-3xl font-bold tabular-nums tracking-tight">
                  {formatCents(data.available.free, "COP")}
                </p>
                <hr style={{ borderColor: "var(--border)" }} />
                <div className="space-y-1">
                  <Row label="Ingreso del mes" faint>
                    <span
                      className="text-sm tabular-nums"
                      style={{ color: "var(--muted-foreground)" }}
                    >
                      {formatCents(data.available.income, "COP")}
                    </span>
                  </Row>
                  {data.available.funds.map((f) => (
                    <Row key={f.fund_id} label={`${nounOf(shapeOf(f))} · ${f.name}`} faint>
                      <span
                        className="text-sm tabular-nums"
                        style={{ color: "var(--muted-foreground)" }}
                      >
                        {formatCents(f.asks, "COP")}
                      </span>
                    </Row>
                  ))}
                  <Row label="Sin fondo que lo cubra" faint>
                    <span
                      className="text-sm tabular-nums"
                      style={{ color: "var(--muted-foreground)" }}
                    >
                      {formatCents(data.available.uncovered, "COP")}
                    </span>
                  </Row>
                </div>
              </div>
            </Section>
          </div>
        )}
      </QueryBoundary>
    </div>
  )
}
