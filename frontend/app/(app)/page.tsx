"use client"

import { useQuery } from "@tanstack/react-query"
import { format } from "date-fns"
import { MoneyAmount } from "@/components/money-amount"
import { ToPayWidget } from "@/components/to-pay-widget"
import { listAccounts } from "@/lib/api/accounts"
import { safeToSpend } from "@/lib/api/budgets"
import { goalsProgress } from "@/lib/api/goals"
import { report as fetchReport } from "@/lib/api/reports"
import { formatCents } from "@/lib/money"
import { qk } from "@/lib/query"

const MONTH = format(new Date(), "yyyy-MM")

const CARD_STYLE = {
  background: "var(--card)",
  boxShadow: "var(--shadow-card)",
  borderRadius: "var(--radius)",
} as const

function Card({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="card-lift p-5 space-y-4" style={CARD_STYLE}>
      <p
        className="text-xs font-medium uppercase tracking-wider"
        style={{ color: "var(--muted-foreground)" }}
      >
        {label}
      </p>
      {children}
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-sm" style={{ color: "var(--muted-foreground)" }}>
        {label}
      </span>
      {children}
    </div>
  )
}

function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`animate-pulse rounded ${className}`} style={{ background: "var(--muted)" }} />
  )
}

export default function DashboardPage() {
  const sts = useQuery({ queryKey: qk.safeToSpend(MONTH), queryFn: () => safeToSpend(MONTH) })
  const report = useQuery({ queryKey: qk.report(MONTH), queryFn: () => fetchReport(MONTH) })
  const goals = useQuery({ queryKey: qk.goalsProgress(), queryFn: () => goalsProgress() })
  const accounts = useQuery({ queryKey: qk.accounts(), queryFn: () => listAccounts() })

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="hero-glow animate-fade-up space-y-1">
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          Disponible para gastar · {MONTH}
        </p>
        {sts.isLoading ? (
          <Skeleton className="h-14 w-64" />
        ) : sts.data ? (
          <p className="font-display text-gradient-mint text-5xl font-bold tabular-nums tracking-tight sm:text-6xl">
            {formatCents(sts.data.free, "COP")}
          </p>
        ) : (
          <p className="text-sm" style={{ color: "var(--expense)" }}>
            No disponible
          </p>
        )}
      </div>

      <hr style={{ borderColor: "var(--border)" }} />

      {/* Por pagar */}
      <div className="animate-fade-up" style={{ animationDelay: "60ms" }}>
        <ToPayWidget />
      </div>

      {/* Grid */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="animate-fade-up" style={{ animationDelay: "90ms" }}>
          <Card label="Ingresos · Gastos · Neto">
            {report.isLoading ? (
              <div className="space-y-2">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-4" />
                ))}
              </div>
            ) : report.data ? (
              <div className="space-y-2.5">
                <Row label="Ingresos">
                  <MoneyAmount
                    cents={report.data.income}
                    currency="COP"
                    type="income"
                    className="text-sm font-medium"
                  />
                </Row>
                <Row label="Gastos">
                  <MoneyAmount
                    cents={report.data.expense}
                    currency="COP"
                    type="expense"
                    className="text-sm font-medium"
                  />
                </Row>
                <hr style={{ borderColor: "var(--border)" }} />
                <Row label="Neto">
                  <span className="text-sm font-semibold tabular-nums">
                    {formatCents(report.data.net, "COP")}
                  </span>
                </Row>
              </div>
            ) : (
              <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                Sin datos
              </p>
            )}
          </Card>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "110ms" }}>
          <Card label="Saldos">
            {accounts.isLoading ? (
              <div className="space-y-2">
                <Skeleton className="h-4" />
                <Skeleton className="h-4" />
              </div>
            ) : accounts.data && accounts.data.filter((a) => !a.archived).length > 0 ? (
              <div className="space-y-2.5">
                {accounts.data
                  .filter((a) => !a.archived)
                  .map((a) => (
                    <Row key={a.id} label={a.name}>
                      <span className="text-sm font-medium tabular-nums">
                        {formatCents(a.balance, a.currency)}
                      </span>
                    </Row>
                  ))}
              </div>
            ) : (
              <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                Sin cuentas
              </p>
            )}
          </Card>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "130ms" }}>
          <Card label="Metas">
            {goals.isLoading ? (
              <Skeleton className="h-16" />
            ) : goals.data && goals.data.length > 0 ? (
              <div className="space-y-4">
                {goals.data.map((g) => {
                  const pct = g.target_amount
                    ? Math.min(100, Math.round((g.saved / g.target_amount) * 100))
                    : null
                  return (
                    <div key={g.goal_id} className="space-y-2">
                      <div className="flex justify-between items-baseline gap-2">
                        <span className="text-sm font-medium truncate">{g.name}</span>
                        <span
                          className="text-xs tabular-nums shrink-0"
                          style={{ color: "var(--muted-foreground)" }}
                        >
                          {pct !== null ? `${pct}%` : formatCents(g.saved, "COP")}
                        </span>
                      </div>
                      {pct !== null && (
                        <div
                          className="h-1.5 rounded-full overflow-hidden"
                          style={{ background: "var(--muted)" }}
                        >
                          <div
                            className="h-full rounded-full"
                            style={{ width: `${pct}%`, background: "var(--primary)" }}
                          />
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                Sin metas activas
              </p>
            )}
          </Card>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "150ms" }}>
          <Card label="Sobres en riesgo">
            {report.isLoading ? (
              <Skeleton className="h-16" />
            ) : report.data ? (
              (() => {
                const over = report.data.envelopes.filter((e) => e.status === "over")
                return over.length > 0 ? (
                  <div className="space-y-2.5">
                    {over.map((e) => (
                      <Row key={e.category} label={e.category}>
                        <MoneyAmount
                          cents={Math.abs(e.available)}
                          currency="COP"
                          type="expense"
                          className="text-sm font-medium"
                        />
                      </Row>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm" style={{ color: "var(--income)" }}>
                    Todos los sobres al día
                  </p>
                )
              })()
            ) : (
              <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                Sin datos
              </p>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}
