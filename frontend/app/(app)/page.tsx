"use client"

import { useQuery } from "@tanstack/react-query"
import { format } from "date-fns"
import { ChatSection } from "@/components/chat/chat-section"
import { EmptyState } from "@/components/empty-state"
import { MoneyAmount } from "@/components/money-amount"
import { PageHeader } from "@/components/page-header"
import { QueryBoundary } from "@/components/query-boundary"
import { HelpExample, HelpSection, ScreenHelp } from "@/components/screen-help"
import { SkeletonBlock, SkeletonText } from "@/components/skeleton"
import { ToPayWidget } from "@/components/to-pay-widget"
import { listAccounts } from "@/lib/api/accounts"
import { moneyAvailable, moneyRates } from "@/lib/api/funds"
import { report as fetchReport } from "@/lib/api/reports"
import type { MonthAvailable } from "@/lib/api/types"
import { nounOf, shapeOf } from "@/lib/funds"
import { formatCents } from "@/lib/money"
import { qk } from "@/lib/query"

const MONTH = format(new Date(), "yyyy-MM")

const ASKS_MORE_THAN_COMES_IN = "Pide más de lo que entra este mes"

const NO_MOVEMENTS_YET = (
  <p>
    Las cifras de esta pantalla salen de los movimientos que registres: cada gasto y cada ingreso.
    Todavía no hay ninguno.
  </p>
)

/**
 * What this screen is, said with the month it is showing.
 *
 * `available` is undefined while the month's figures are loading and when they
 * never arrive at all (AC-16), so the worked example is the fallback for both.
 */
function DashboardHelp({ available }: { available: MonthAvailable | undefined }) {
  const live = available !== undefined && (available.income > 0 || available.funds.length > 0)
  const askingTooMuch = available?.funds.filter((fund) => fund.asks > available.income) ?? []
  return (
    <>
      <p>
        Esta pantalla resume el mes: lo que entra, lo que cada fondo y cada presupuesto pide, y lo
        que queda libre después de eso.
      </p>
      {live && available !== undefined ? (
        <>
          <p>Este mes entran {formatCents(available.income, "COP")}.</p>
          <HelpSection lead="Cada uno pide:">
            {available.funds.map((fund) => (
              <li key={fund.fund_id}>
                {`${fund.name} (${shapeOf(fund)}) — pide ${formatCents(fund.asks, "COP")}`}
              </li>
            ))}
          </HelpSection>
          {askingTooMuch.length > 0 && (
            <HelpSection lead={`${ASKS_MORE_THAN_COMES_IN}:`} label={ASKS_MORE_THAN_COMES_IN}>
              {askingTooMuch.map((fund) => (
                <li key={fund.fund_id}>
                  {`${fund.name} — pide ${formatCents(fund.asks, "COP")} y este mes entran ${formatCents(available.income, "COP")}.`}
                </li>
              ))}
            </HelpSection>
          )}
        </>
      ) : (
        <HelpExample>
          <li>
            Por ejemplo: entran $ 3.000.000 en el mes. Un fondo de Mercado pide $ 500.000 y un
            presupuesto de Restaurantes pide $ 200.000, así que quedan $ 2.300.000 libres.
          </li>
        </HelpExample>
      )}
    </>
  )
}

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

export default function DashboardPage() {
  const available = useQuery({
    queryKey: qk.moneyAvailable(MONTH),
    queryFn: () => moneyAvailable(MONTH),
  })
  const rates = useQuery({ queryKey: qk.moneyRates(MONTH), queryFn: () => moneyRates(MONTH) })
  const report = useQuery({ queryKey: qk.report(MONTH), queryFn: () => fetchReport(MONTH) })
  const accounts = useQuery({ queryKey: qk.accounts(), queryFn: () => listAccounts() })

  return (
    <div className="space-y-8">
      <PageHeader
        title="Dashboard"
        titleHidden
        help={
          <ScreenHelp screen="Dashboard">
            <DashboardHelp available={available.data} />
          </ScreenHelp>
        }
      />

      {/* Hero */}
      <div className="hero-glow animate-fade-up space-y-1">
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          Disponible este mes · {MONTH}
        </p>
        <QueryBoundary
          query={available}
          skeleton={<SkeletonBlock className="h-14 w-64" />}
          errorMessage="No se pudo cargar el disponible"
        >
          {(data) => (
            <p
              data-slot="money-available"
              className="font-display text-gradient-mint text-5xl font-bold tabular-nums tracking-tight sm:text-6xl"
            >
              {formatCents(data.free, "COP")}
            </p>
          )}
        </QueryBoundary>
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
            <QueryBoundary
              query={report}
              skeleton={<SkeletonText lines={3} />}
              empty={{
                when: (d) => d.income === 0 && d.expense === 0,
                node: (
                  <EmptyState
                    message="Todavía no has registrado movimientos."
                    description={NO_MOVEMENTS_YET}
                    action={{ label: "Registrar el primero", href: "/transactions" }}
                  />
                ),
              }}
            >
              {(data) => (
                <div className="space-y-2.5">
                  <Row label="Ingresos">
                    <MoneyAmount
                      cents={data.income}
                      currency="COP"
                      type="income"
                      className="text-sm font-medium"
                    />
                  </Row>
                  <Row label="Gastos">
                    <MoneyAmount
                      cents={data.expense}
                      currency="COP"
                      type="expense"
                      className="text-sm font-medium"
                    />
                  </Row>
                  <hr style={{ borderColor: "var(--border)" }} />
                  <Row label="Neto">
                    <span className="text-sm font-semibold tabular-nums">
                      {formatCents(data.net, "COP")}
                    </span>
                  </Row>
                </div>
              )}
            </QueryBoundary>
          </Card>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "110ms" }}>
          <Card label="Saldos">
            <QueryBoundary
              query={accounts}
              skeleton={<SkeletonText lines={2} />}
              empty={{
                when: (d) => d.filter((a) => !a.archived).length === 0,
                node: (
                  <EmptyState
                    message="Sin cuentas"
                    action={{ label: "Crear cuenta", href: "/accounts" }}
                  />
                ),
              }}
            >
              {(data) => (
                <div className="space-y-2.5">
                  {data
                    .filter((a) => !a.archived)
                    .map((a) => (
                      <Row key={a.id} label={a.name}>
                        <span className="text-sm font-medium tabular-nums">
                          {formatCents(a.balance, a.currency)}
                        </span>
                      </Row>
                    ))}
                </div>
              )}
            </QueryBoundary>
          </Card>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "130ms" }}>
          <Card label="De dónde sale el disponible">
            <QueryBoundary
              query={available}
              skeleton={<SkeletonText lines={3} />}
              errorMessage="No se pudo cargar el desglose"
            >
              {(data) => (
                <div className="space-y-2.5">
                  <Row label="Ingreso del mes">
                    <MoneyAmount
                      cents={data.income}
                      currency="COP"
                      type="income"
                      className="text-sm font-medium"
                    />
                  </Row>
                  {data.funds.map((fund) => (
                    <Row key={fund.fund_id} label={`${nounOf(shapeOf(fund))} · ${fund.name}`}>
                      <MoneyAmount
                        cents={fund.asks}
                        currency="COP"
                        type="expense"
                        className="text-sm font-medium"
                      />
                    </Row>
                  ))}
                  <Row label="Sin fondo que lo cubra">
                    <MoneyAmount
                      cents={data.uncovered}
                      currency="COP"
                      type="expense"
                      className="text-sm font-medium"
                    />
                  </Row>
                  <hr style={{ borderColor: "var(--border)" }} />
                  <Row label="Disponible">
                    <span className="text-sm font-semibold tabular-nums">
                      {formatCents(data.free, "COP")}
                    </span>
                  </Row>
                </div>
              )}
            </QueryBoundary>
          </Card>
        </div>

        <div className="animate-fade-up" style={{ animationDelay: "150ms" }}>
          <Card label="Tasas · lo que ganas y lo que cuestas al mes">
            <QueryBoundary
              query={rates}
              skeleton={<SkeletonText lines={3} />}
              errorMessage="No se pudieron cargar las tasas"
            >
              {(data) => (
                <div className="space-y-2.5">
                  <Row label="Ganas al mes">
                    <MoneyAmount
                      cents={data.earning}
                      currency="COP"
                      type="income"
                      className="text-sm font-medium"
                    />
                  </Row>
                  <Row label="Cuestas al mes">
                    <MoneyAmount
                      cents={data.cost}
                      currency="COP"
                      type="expense"
                      className="text-sm font-medium"
                    />
                  </Row>
                  <hr style={{ borderColor: "var(--border)" }} />
                  <Row label="Margen">
                    <span className="text-sm font-semibold tabular-nums">
                      {formatCents(data.margin, "COP")}
                    </span>
                  </Row>
                  <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                    Una tasa no es el disponible: reparte cada ciclo entre sus meses.
                  </p>
                </div>
              )}
            </QueryBoundary>
          </Card>
        </div>
      </div>

      <ChatSection />
    </div>
  )
}
