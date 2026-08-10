"use client"

import { useQuery } from "@tanstack/react-query"
import { format } from "date-fns"
import Link from "next/link"
import { ChatSection } from "@/components/chat/chat-section"
import { EmptyState } from "@/components/empty-state"
import { Minus, Section, Term, Total } from "@/components/ledger"
import { MoneyAmount } from "@/components/money-amount"
import { PageHeader } from "@/components/page-header"
import { QueryBoundary } from "@/components/query-boundary"
import { HelpExample, HelpSection, ScreenHelp } from "@/components/screen-help"
import { SkeletonBlock, SkeletonText } from "@/components/skeleton"
import { ToPayWidget } from "@/components/to-pay-widget"
import { listAccounts } from "@/lib/api/accounts"
import { moneyRates } from "@/lib/api/funds"
import { monthSplit } from "@/lib/api/metas"
import { report as fetchReport } from "@/lib/api/reports"
import type { MetaStatus, MonthAvailable } from "@/lib/api/types"
import { availableRows } from "@/lib/available-breakdown"
import { shapeOf } from "@/lib/funds"
import { gaveBackLabelOf } from "@/lib/metas"
import { formatCents } from "@/lib/money"
import { qk } from "@/lib/query"

const MONTH = format(new Date(), "yyyy-MM")

const ASKS_MORE_THAN_COMES_IN = "Pide más de lo que entra este mes"

/**
 * The metas whose month has passed with nothing bought (AC-19).
 *
 * They are full and asking for nothing, so no figure on this screen moves for
 * them — which is exactly why the screen has to name them: the owner is the one
 * being waited on, to link the purchase, close the meta or move its date.
 */
function WaitingMetas({ metas }: { metas: MetaStatus[] }) {
  const waiting = metas.filter((meta) => meta.waiting)
  if (waiting.length === 0) return null
  return (
    <p className="max-w-prose text-sm" style={{ color: "var(--muted-foreground)" }}>
      {waiting.map((meta) => meta.name).join(", ")}{" "}
      {waiting.length === 1 ? "está esperando" : "están esperando"}: su mes ya pasó y no le
      {waiting.length === 1 ? "" : "s"} has enlazado la compra.{" "}
      <Link href="/metas" className="underline">
        Ir a metas
      </Link>
    </p>
  )
}

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

export default function DashboardPage() {
  const report = useQuery({ queryKey: qk.report(MONTH), queryFn: () => fetchReport(MONTH) })
  const split = useQuery({ queryKey: qk.metaSplit(MONTH), queryFn: () => monthSplit(MONTH) })
  const rates = useQuery({ queryKey: qk.moneyRates(MONTH), queryFn: () => moneyRates(MONTH) })
  const accounts = useQuery({ queryKey: qk.accounts(), queryFn: () => listAccounts() })
  const negative = (report.data?.available.free ?? 0) < 0

  return (
    <div className="animate-fade-up space-y-8">
      <PageHeader
        title="Dashboard"
        titleHidden
        help={
          <ScreenHelp screen="Dashboard">
            <DashboardHelp available={report.data?.available} />
          </ScreenHelp>
        }
      />

      <div className="space-y-5">
        <div className="space-y-1">
          <p className="text-xs font-medium" style={{ color: "var(--muted-foreground)" }}>
            Disponible este mes · {MONTH}
          </p>
          <QueryBoundary
            query={report}
            skeleton={<SkeletonBlock className="h-12 w-64" />}
            errorMessage="No se pudo cargar el disponible"
          >
            {(data) => (
              <p
                data-slot="money-available"
                className="text-[2.5rem] font-semibold leading-[1.05] tabular-nums tracking-tight"
                style={negative ? { color: "var(--expense)" } : undefined}
              >
                {formatCents(data.available.free, "COP")}
              </p>
            )}
          </QueryBoundary>
        </div>

        <QueryBoundary
          query={report}
          skeleton={<SkeletonText lines={3} />}
          errorMessage="No se pudo cargar el desglose"
        >
          {({ available: data }) => (
            <div className="max-w-lg">
              {availableRows(data).map((row) => (
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
              <Total label="Disponible" cents={data.free} />
            </div>
          )}
        </QueryBoundary>

        {report.data && <WaitingMetas metas={report.data.available.metas} />}
      </div>

      <hr style={{ borderColor: "var(--border)" }} />

      <ToPayWidget />

      <hr style={{ borderColor: "var(--border)" }} />

      <div className="grid gap-8 sm:grid-cols-2">
        <Section label="Saldos">
          <QueryBoundary
            query={accounts}
            skeleton={<SkeletonText lines={3} />}
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
              <div>
                {data
                  .filter((a) => !a.archived)
                  .map((a) => (
                    <Term key={a.id} label={a.name}>
                      <span className="text-sm font-medium tabular-nums">
                        {formatCents(a.balance, a.currency)}
                      </span>
                    </Term>
                  ))}
              </div>
            )}
          </QueryBoundary>
        </Section>

        <Section label="A dónde se va el mes">
          <QueryBoundary
            query={split}
            skeleton={<SkeletonText lines={4} />}
            errorMessage="No se pudo cargar el reparto del mes"
          >
            {(data) => (
              <div>
                <Term label="Ahorro · fondos y metas">
                  <span className="text-sm font-medium tabular-nums">
                    {formatCents(data.set_aside, "COP")}
                    <span className="ml-2 font-normal" style={{ color: "var(--muted-foreground)" }}>
                      {data.set_aside_share}%
                    </span>
                  </span>
                </Term>
                {data.gave_back.map((meta) => (
                  <Term key={meta.meta_id} label={gaveBackLabelOf(meta)}>
                    <MoneyAmount
                      cents={-meta.released}
                      currency="COP"
                      className="text-sm font-medium"
                    />
                  </Term>
                ))}
                <Term label="Consumo · lo que se gastó">
                  <MoneyAmount
                    cents={data.consumo}
                    currency="COP"
                    className="text-sm font-medium"
                  />
                </Term>
                <Term label="Libre · nadie lo reclamó">
                  <MoneyAmount cents={data.libre} currency="COP" className="text-sm font-medium" />
                </Term>
                <Total label="Ingreso del mes" cents={data.income} />
              </div>
            )}
          </QueryBoundary>
        </Section>

        <Section label="Ingresos · gastos · neto">
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
              <div>
                <Term label="Ingresos">
                  <MoneyAmount
                    cents={data.income}
                    currency="COP"
                    type="income"
                    className="text-sm font-medium"
                  />
                </Term>
                <Term label="Gastos">
                  <MoneyAmount
                    cents={data.expense}
                    currency="COP"
                    type="expense"
                    className="text-sm font-medium"
                  />
                </Term>
                <Total label="Neto" cents={data.net} />
              </div>
            )}
          </QueryBoundary>
        </Section>

        <Section label="Tasas · lo que ganas y lo que cuestas al mes">
          <QueryBoundary
            query={rates}
            skeleton={<SkeletonText lines={3} />}
            errorMessage="No se pudieron cargar las tasas"
          >
            {(data) => (
              <div>
                <Term label="Ganas al mes">
                  <MoneyAmount
                    cents={data.earning}
                    currency="COP"
                    type="income"
                    className="text-sm font-medium"
                  />
                </Term>
                <Term label="Cuestas al mes">
                  <MoneyAmount
                    cents={data.cost}
                    currency="COP"
                    type="expense"
                    className="text-sm font-medium"
                  />
                </Term>
                <Total label="Margen" cents={data.margin} />
                <p
                  className="mt-3 max-w-prose text-xs"
                  style={{ color: "var(--muted-foreground)" }}
                >
                  Una tasa no es el disponible: reparte cada ciclo entre sus meses.
                </p>
              </div>
            )}
          </QueryBoundary>
        </Section>
      </div>

      <ChatSection />
    </div>
  )
}
