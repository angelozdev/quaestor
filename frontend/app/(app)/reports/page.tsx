"use client"

import { useQuery } from "@tanstack/react-query"
import { format } from "date-fns"
import { useState } from "react"
import { DataTable } from "@/components/data-table"
import { EmptyState } from "@/components/empty-state"
import { Minus, Section, Term, Total } from "@/components/ledger"
import { MoneyAmount } from "@/components/money-amount"
import { PageHeader } from "@/components/page-header"
import { QueryBoundary } from "@/components/query-boundary"
import { ScreenHelp } from "@/components/screen-help"
import { SkeletonCard } from "@/components/skeleton"
import { report } from "@/lib/api/reports"
import { availableRows } from "@/lib/available-breakdown"
import { formatCents } from "@/lib/money"
import { qk } from "@/lib/query"
import { Input } from "@/ui"

const WHERE_THE_MONTH_WENT = (
  <p>Este reporte muestra a dónde se fue el gasto del mes, repartido por categoría y por grupo.</p>
)

const REPORTS_HELP = (
  <>
    {WHERE_THE_MONTH_WENT}
    <p>
      Debajo del reparto están el resultado del mes —ingresos contra gastos— y de dónde sale el
      disponible. Cambia el mes arriba a la derecha para leer cualquier otro.
    </p>
  </>
)

function Share({ cents, pct }: { cents: number; pct: number }) {
  return (
    <span className="flex shrink-0 items-baseline gap-3">
      <span className="text-sm font-medium tabular-nums">{formatCents(cents, "COP")}</span>
      <span
        className="w-11 text-right text-xs tabular-nums"
        style={{ color: "var(--muted-foreground)" }}
      >
        {pct.toFixed(1)}%
      </span>
    </span>
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
          <Input
            type="month"
            aria-label="Mes del reporte"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="w-40"
          />
        }
        help={<ScreenHelp screen="Reportes">{REPORTS_HELP}</ScreenHelp>}
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
          <div className="animate-fade-up space-y-10">
            <section className="space-y-4">
              <div className="space-y-1">
                <p className="text-xs font-medium" style={{ color: "var(--muted-foreground)" }}>
                  Neto del mes
                </p>
                <p
                  className="text-[2.5rem] font-semibold leading-[1.05] tabular-nums tracking-tight"
                  style={{ color: data.net >= 0 ? "var(--income)" : "var(--expense)" }}
                >
                  {formatCents(data.net, "COP")}
                </p>
              </div>
              <div className="max-w-lg">
                <Term label="Ingresos">
                  <MoneyAmount
                    cents={data.income}
                    currency="COP"
                    type="income"
                    className="text-sm font-medium"
                  />
                </Term>
                <Term label="Gastos">
                  <span className="flex items-baseline gap-1.5">
                    <Minus />
                    <MoneyAmount
                      cents={data.expense}
                      currency="COP"
                      className="text-sm font-medium"
                    />
                  </span>
                </Term>
                <Total label="Neto" cents={data.net} />
              </div>
              {data.drift_mom && (
                <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                  vs {data.drift_mom.prev_month} →{" "}
                  <span
                    className="tabular-nums"
                    style={{
                      color: data.drift_mom.net_abs >= 0 ? "var(--income)" : "var(--expense)",
                    }}
                  >
                    {data.drift_mom.net_abs >= 0 ? "+" : ""}
                    {formatCents(data.drift_mom.net_abs, "COP")}
                  </span>
                </p>
              )}
            </section>

            <Section label="Fondos y presupuestos">
              <DataTable
                rows={data.funds}
                rowKey={(f) => f.category_name}
                pageSize={100}
                emptyMessage="Sin fondos este mes"
                emptyAction={{ label: "Ir a fondos", href: "/funds" }}
                columns={[
                  {
                    key: "category",
                    header: "Categoría",
                    render: (f) => f.category_name,
                  },
                  {
                    key: "asks",
                    header: "Pidió",
                    align: "right",
                    render: (f) => formatCents(f.asks, "COP"),
                  },
                  {
                    key: "spent",
                    header: "Gastado",
                    align: "right",
                    render: (f) => formatCents(f.spent, "COP"),
                  },
                  {
                    key: "holds",
                    header: "Tiene",
                    align: "right",
                    render: (f) => (
                      <span
                        className="font-medium"
                        style={{ color: f.on_track ? undefined : "var(--expense)" }}
                      >
                        {formatCents(f.holds, "COP")}
                      </span>
                    ),
                  },
                ]}
              />
            </Section>

            <Section label="Metas">
              <DataTable
                rows={data.metas}
                rowKey={(m) => m.meta_name}
                pageSize={100}
                emptyMessage="Sin metas este mes"
                emptyAction={{ label: "Ir a metas", href: "/metas" }}
                columns={[
                  { key: "meta", header: "Meta", render: (m) => m.meta_name },
                  {
                    key: "asks",
                    header: "Pidió",
                    align: "right",
                    render: (m) => formatCents(m.asks, m.currency),
                  },
                  {
                    key: "holds",
                    header: "Lleva",
                    align: "right",
                    render: (m) => (
                      <span className="font-medium">{formatCents(m.holds, m.currency)}</span>
                    ),
                  },
                ]}
              />
              <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                Entre fondos y metas, el mes pide {formatCents(data.asked, "COP")}.
              </p>
            </Section>

            <div className="grid gap-x-12 gap-y-10 sm:grid-cols-2">
              <Section label="Por categoría">
                {data.by_category.length > 0 ? (
                  <div>
                    {data.by_category.map((c) => (
                      <Term key={c.category} label={c.category}>
                        <Share cents={c.total} pct={c.pct} />
                      </Term>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    message="Sin gastos este mes"
                    description={WHERE_THE_MONTH_WENT}
                    action={{ label: "Registrar un movimiento", href: "/transactions" }}
                  />
                )}
              </Section>

              <Section label="Por grupo">
                {data.by_group.length > 0 ? (
                  <div>
                    {data.by_group.map((g) => (
                      <Term key={g.group} label={g.group}>
                        <Share cents={g.total} pct={g.pct} />
                      </Term>
                    ))}
                  </div>
                ) : (
                  <EmptyState message="Sin gastos agrupados este mes" />
                )}
              </Section>
            </div>

            <Section label="Disponible · cierre">
              <div className="max-w-lg">
                {availableRows(data.available).map((row) => (
                  <Term key={row.key} label={row.label}>
                    <span className="flex items-baseline gap-1.5">
                      {row.kind === "claim" && row.cents > 0 && <Minus />}
                      <MoneyAmount
                        cents={row.cents}
                        currency="COP"
                        type={row.kind === "income" ? "income" : undefined}
                        className="text-sm font-medium"
                      />
                    </span>
                  </Term>
                ))}
                <Total label="Disponible" cents={data.available.free} />
              </div>
            </Section>
          </div>
        )}
      </QueryBoundary>
    </div>
  )
}
