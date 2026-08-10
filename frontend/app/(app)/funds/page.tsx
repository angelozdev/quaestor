"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { useState } from "react"
import { toast } from "sonner"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState } from "@/components/empty-state"
import { PageHeader } from "@/components/page-header"
import { QueryBoundary } from "@/components/query-boundary"
import { HelpExample, HelpSection, ScreenHelp } from "@/components/screen-help"
import { SkeletonRows } from "@/components/skeleton"
import { StatusBadge } from "@/components/status-badge"
import { deleteFund, listFunds, moneyAvailable } from "@/lib/api/funds"
import type { FundStatus } from "@/lib/api/types"
import { ApiError } from "@/lib/api/types"
import { monthNameOf, nextYearMonth } from "@/lib/date"
import { type FundShape, nounOf, shapeOf, shapeSentence, whatItIs } from "@/lib/funds"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Button, Input } from "@/ui"
import { CreateFundForm } from "./create-form"
import { ruleLabel } from "./rules"

const SECTIONS: { shape: FundShape; heading: string; says: string }[] = [
  {
    shape: "presupuesto",
    heading: "PRESUPUESTOS — topes del mes",
    says: "Lo que no gastes no se guarda.",
  },
  {
    shape: "fondo",
    heading: "FONDOS — van juntando",
    says: "Lo que sobre pasa al mes siguiente.",
  },
]

/** What one shape is, with its noun picked out — the same claim wherever it is made. */
function ShapeIs({ shape }: { shape: FundShape }) {
  return (
    <>
      Un <strong>{shape}</strong> {whatItIs(shape)}
    </>
  )
}

const NOTHING_YET = (
  <>
    <p>
      <ShapeIs shape="fondo" /> — para el mantenimiento del carro, o para pagar una suscripción
      anual mes a mes.
    </p>
    <p>
      <ShapeIs shape="presupuesto" />.
    </p>
  </>
)

/** Why the entry asks what it asks, in the words of the rule that decides it. */
function whyItAsks(fund: FundStatus, shape: FundShape): string {
  if (fund.rule === "average") return "porque es el promedio de lo que gastaste antes"
  if (fund.rule === "from-recurring") return "porque es lo que piden sus cobros registrados"
  return shape === "presupuesto"
    ? "porque ese es el tope que pusiste"
    : "porque ese es el monto que decidiste apartar"
}

/** One entry as the panel says it: its shape, its figure, and what it does next month. */
function panelLine(fund: FundStatus): string {
  const shape = shapeOf(fund)
  const next = monthNameOf(nextYearMonth(fund.year_month)).toLowerCase()
  const leftover =
    shape === "fondo" ? `Lo que sobre pasa a ${next}.` : `Lo que sobre no pasa a ${next}.`
  return `${fund.name} es un ${shape} — pide ${formatCents(fund.asks, "COP")} este mes ${whyItAsks(fund, shape)}. ${leftover}`
}

/**
 * What this screen is, said with the entries it is showing.
 *
 * `funds` is undefined while the month's figures are loading and when they
 * never arrive at all (AC-16), so the worked example is the fallback for both.
 */
function FundsHelp({ funds, month }: { funds: FundStatus[] | undefined; month: string }) {
  const next = monthNameOf(nextYearMonth(month)).toLowerCase()
  return (
    <>
      <p>
        <ShapeIs shape="fondo" />. <ShapeIs shape="presupuesto" />.
      </p>
      {funds !== undefined && funds.length > 0 ? (
        <HelpSection lead="Lo que tienes en esta pantalla:">
          {funds.map((fund) => (
            <li key={fund.fund_id}>{panelLine(fund)}</li>
          ))}
        </HelpSection>
      ) : (
        <HelpExample>
          <li>
            Por ejemplo: Restaurantes, un presupuesto de $ 100.000 al mes. Si gastas $ 60.000,{" "}
            {next} vuelve a empezar en $ 100.000 y los $ 40.000 que sobraron no se guardan.
          </li>
          <li>
            Por ejemplo: Tecnología, un fondo de $ 100.000 al mes. Si gastas $ 60.000, {next} abre
            con $ 140.000 porque los $ 40.000 que sobraron se quedan.
          </li>
        </HelpExample>
      )}
    </>
  )
}

/** What the month did to the entry, and what it leaves behind. */
function keptLine(fund: FundStatus): string {
  const spent = formatCents(fund.spent, "COP")
  if (shapeOf(fund) === "fondo") {
    return `Gastaste ${spent} · se guardan ${formatCents(fund.carries, "COP")}`
  }
  const lost = Math.max(fund.asks - fund.spent, 0)
  return `Gastaste ${spent} · los ${formatCents(lost, "COP")} que sobran no se guardan`
}

/** What the next month opens with, named by its own month. */
function nextMonthLine(fund: FundStatus): string {
  const next = monthNameOf(nextYearMonth(fund.year_month))
  const has = formatCents(fund.next_month_has, "COP")
  return shapeOf(fund) === "fondo"
    ? `${next} tendrá ${has} para gastar.`
    : `${next} vuelve a ${has}.`
}

function FundRow({
  fund,
  startedThisMonth,
  onDelete,
}: {
  fund: FundStatus
  startedThisMonth: boolean
  onDelete: () => void
}) {
  const shape = shapeOf(fund)
  return (
    <tr
      className="border-t transition-colors hover:bg-[var(--muted)]"
      style={{ borderColor: "var(--border)" }}
    >
      <td className="px-3 py-2 align-top">
        <div className="space-y-1">
          <p className="font-medium">{fund.name}</p>
          <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
            {keptLine(fund)}
          </p>
          <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
            {nextMonthLine(fund)}
          </p>
          {startedThisMonth && fund.holds === 0 && (
            <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
              Tiene $0 porque empezó este mes.
            </p>
          )}
        </div>
      </td>
      <td className="px-3 py-2 align-top" style={{ color: "var(--muted-foreground)" }}>
        {ruleLabel(fund.rule, shape)}
      </td>
      <td className="px-3 py-2.5 text-right align-top tabular-nums">
        {formatCents(fund.asks, "COP")}
      </td>
      <td className="px-3 py-2.5 text-right align-top tabular-nums">
        {formatCents(fund.holds, "COP")}
      </td>
      <td className="px-3 py-2 align-top">
        <StatusBadge kind="onTrack" value={fund.on_track} />
      </td>
      <td className="px-3 py-2.5 text-right align-top">
        <Button
          variant="ghost"
          size="sm"
          aria-label={`Eliminar el ${shape} de ${fund.name}`}
          onClick={onDelete}
        >
          Eliminar
        </Button>
      </td>
    </tr>
  )
}

function FundSection({
  shape,
  heading,
  says,
  funds,
  startMonths,
  month,
  onDelete,
}: {
  shape: FundShape
  heading: string
  says: string
  funds: FundStatus[]
  startMonths: Map<number, string>
  month: string
  onDelete: (fund: FundStatus) => void
}) {
  const headingId = `heading-${shape}`
  return (
    <section aria-labelledby={headingId} className="space-y-2">
      <h2 id={headingId} className="text-xs font-semibold">
        {heading}
      </h2>
      <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
        {says}
      </p>
      {funds.length === 0 ? (
        <p className="max-w-prose py-2 text-sm" style={{ color: "var(--muted-foreground)" }}>
          {`Todavía no tienes ${shape}s. ${shapeSentence(shape)}.`}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table aria-labelledby={headingId} className="w-full text-sm">
            <thead>
              <tr
                className="hairline-total"
                style={{ color: "var(--muted-foreground)", borderTop: "none" }}
              >
                <th className="px-3 pb-2 text-left text-xs font-medium uppercase tracking-wide">
                  Categoría
                </th>
                <th className="px-3 pb-2 text-left text-xs font-medium uppercase tracking-wide">
                  Regla
                </th>
                <th className="px-3 pb-2 text-right text-xs font-medium uppercase tracking-wide">
                  Pide
                </th>
                <th className="px-3 pb-2 text-right text-xs font-medium uppercase tracking-wide">
                  Tiene
                </th>
                <th className="px-3 pb-2 text-left text-xs font-medium uppercase tracking-wide">
                  Estado
                </th>
                <th className="w-28 px-3 pb-2" />
              </tr>
            </thead>
            <tbody>
              {funds.map((fund) => (
                <FundRow
                  key={fund.fund_id}
                  fund={fund}
                  startedThisMonth={startMonths.get(fund.fund_id) === month}
                  onDelete={() => onDelete(fund)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export default function FundsPage() {
  const [month, setMonth] = useState(format(new Date(), "yyyy-MM"))
  const [making, setMaking] = useState<FundShape | null>(null)
  const [deleting, setDeleting] = useState<FundStatus | null>(null)
  const qc = useQueryClient()

  const view = useQuery({
    queryKey: qk.moneyAvailable(month),
    queryFn: () => moneyAvailable(month),
  })
  const lines = useQuery({ queryKey: qk.funds(), queryFn: () => listFunds() })

  const startMonths = new Map((lines.data ?? []).map((line) => [line.fund_id, line.start_month]))
  const heldBy = new Map(
    (view.data?.funds ?? []).map((fund) => [fund.category_id, shapeOf(fund)] as const),
  )

  const remove = useMutation({
    mutationFn: (fund: FundStatus) => deleteFund(fund.fund_id),
    onSuccess: (_result, fund) => {
      toast.success(`${nounOf(shapeOf(fund))} eliminado`)
      invalidate(qc, "fundWrite")
      setDeleting(null)
    },
    onError: (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error"),
  })

  const deletingShape = deleting === null ? "fondo" : shapeOf(deleting)

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fondos y presupuestos"
        subtitle={month}
        action={
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Input
              type="month"
              aria-label="Mes"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="w-40"
            />
            <Button variant="outline" onClick={() => setMaking("presupuesto")}>
              + Nuevo presupuesto
            </Button>
            <Button onClick={() => setMaking("fondo")}>+ Nuevo fondo</Button>
          </div>
        }
        help={
          <ScreenHelp screen="Fondos y presupuestos">
            <FundsHelp funds={view.data?.funds} month={month} />
          </ScreenHelp>
        }
      />

      {making !== null && (
        <CreateFundForm
          key={making}
          shape={making}
          month={month}
          heldBy={heldBy}
          onDone={() => setMaking(null)}
          onCancel={() => setMaking(null)}
        />
      )}

      <QueryBoundary
        query={view}
        skeleton={<SkeletonRows rows={5} />}
        errorMessage="No se pudieron cargar los fondos y presupuestos"
        empty={{
          when: (data) => data.funds.length === 0,
          node: (
            <EmptyState
              message="Todavía no tienes fondos ni presupuestos."
              description={NOTHING_YET}
              action={[
                {
                  label: "Crear mi primer presupuesto",
                  onClick: () => setMaking("presupuesto"),
                },
                { label: "Crear mi primer fondo", onClick: () => setMaking("fondo") },
              ]}
            />
          ),
        }}
      >
        {(data) => (
          <div className="space-y-8">
            {SECTIONS.map((section) => (
              <FundSection
                key={section.shape}
                shape={section.shape}
                heading={section.heading}
                says={section.says}
                funds={data.funds.filter((fund) => shapeOf(fund) === section.shape)}
                startMonths={startMonths}
                month={month}
                onDelete={setDeleting}
              />
            ))}
          </div>
        )}
      </QueryBoundary>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title={`Eliminar ${deletingShape}`}
        description={`Se elimina el ${deletingShape} de "${deleting?.name}". La categoría y sus movimientos no cambian.`}
        confirmLabel="Eliminar"
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
      />
    </div>
  )
}
