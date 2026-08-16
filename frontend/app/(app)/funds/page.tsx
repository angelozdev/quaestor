"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { useState } from "react"
import { toast } from "sonner"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState } from "@/components/empty-state"
import { Section } from "@/components/ledger"
import { PageHeader } from "@/components/page-header"
import { QueryBoundary } from "@/components/query-boundary"
import { HelpExample, HelpSection, ScreenHelp } from "@/components/screen-help"
import { SkeletonRows } from "@/components/skeleton"
import { StatusBadge } from "@/components/status-badge"
import { deleteFund, listFunds, moneyAvailable } from "@/lib/api/funds"
import type { FundCharge, FundStatus } from "@/lib/api/types"
import { ApiError } from "@/lib/api/types"
import { monthAndYearOf, monthNameOf, nextYearMonth } from "@/lib/date"
import { type FundShape, nounOf, shapeOf, shapeSentence, whatItIs } from "@/lib/funds"
import { formatCents, sharesAddingTo } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Button, Input } from "@/ui"
import { CreateFundForm } from "./create-form"
import { ruleLabel } from "./rules"

/** What the table says about each entry, in the order it says it. */
const COLUMNS = [
  { label: "Categoría", align: "text-left" },
  { label: "Regla", align: "text-left" },
  { label: "Pide", align: "text-right" },
  { label: "Tiene", align: "text-right" },
  { label: "Estado", align: "text-left" },
]

const SECTIONS: { shape: FundShape; heading: string; says: string }[] = [
  {
    shape: "presupuesto",
    heading: "Presupuestos — topes del mes",
    says: "Lo que no gastes no se guarda.",
  },
  {
    shape: "fondo",
    heading: "Fondos — van juntando",
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
  return `${fund.name} es un ${shape} — pide ${formatCents(fund.asks, fund.currency)} este mes ${whyItAsks(fund, shape)}. ${leftover}`
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
  const spent = formatCents(fund.spent, fund.currency)
  if (shapeOf(fund) === "fondo") {
    return `Gastaste ${spent} · se guardan ${formatCents(fund.carries, fund.currency)}`
  }
  const lost = Math.max(fund.asks - fund.spent, 0)
  return `Gastaste ${spent} · los ${formatCents(lost, fund.currency)} que sobran no se guardan`
}

/** What the next month opens with, named by its own month. */
function nextMonthLine(fund: FundStatus): string {
  const next = monthNameOf(nextYearMonth(fund.year_month))
  const has = formatCents(fund.next_month_has, fund.currency)
  return shapeOf(fund) === "fondo"
    ? `${next} tendrá ${has} para gastar.`
    : `${next} vuelve a ${has}.`
}

/**
 * What one charge contributes, and whether it leaves this month or stays.
 *
 * The whole charge is named only when it differs from the share, which is
 * what makes the share legible: $ 100.000 means nothing until it is read as a
 * twelfth of $ 1.200.000 (AC-2).
 *
 * `shownAsks` is the share after the row's rounding has been shared out, so the
 * lines add up to the figure above them (AC-4). It is the charge's own share to
 * the peso, and differs from `asks` by centavos only.
 */
function chargeLine(
  charge: FundCharge,
  month: string,
  shownAsks: number,
  currency: string,
): string {
  const when =
    charge.charge_month === month
      ? "vence este mes"
      : `se guarda para ${monthAndYearOf(charge.charge_month)}`
  const share = formatCents(shownAsks, currency)
  const figure =
    charge.asks === charge.costs ? share : `${share} de ${formatCents(charge.costs, currency)}`
  return `${charge.name} — ${when} · ${figure}`
}

/**
 * Why a fund that fills for charges is asking nothing at all this month.
 *
 * A fund that hangs off one charge gets its own sentence. Its category may hold
 * plenty of other charges, so saying the category ran out would be false; what
 * ran out is this charge's turns. And the way out is the box on Recurrentes,
 * not a delete button that no longer carries that name.
 */
function nothingToSetAside(fund: FundStatus): string {
  if (fund.has_repeating_charges)
    return "Este mes no hay nada que apartar: sus cobros están omitidos o ya pagados."
  if (fund.recurring_id !== null)
    return `${fund.name} ya no vuelve a cobrar, así que pedirá 0 siempre. Destíldalo en Recurrentes.`
  return "La categoría ya no tiene cobros recurrentes, así que pedirá $ 0 siempre. Bórralo, o registra un cobro."
}

/**
 * The charges behind the figure, always under the row it explains.
 *
 * Only the rule that fills for charges has any — a fixed or averaged fund's
 * figure is a single number the owner stated or the app averaged, and there is
 * nothing to open it into.
 */
function FundCharges({ fund }: { fund: FundStatus }) {
  if (fund.rule !== "from-recurring") return null
  const shown = sharesAddingTo(
    fund.charges.map((charge) => charge.asks),
    fund.asks,
  )
  const held = fund.currency
  return (
    <tr>
      <td
        colSpan={COLUMNS.length + 1}
        className="px-3 pb-2.5"
        style={{ color: "var(--muted-foreground)" }}
      >
        {fund.charges.length === 0 ? (
          <p className="text-xs">{nothingToSetAside(fund)}</p>
        ) : (
          <ul className="space-y-0.5">
            {fund.charges.map((charge, index) => (
              <li key={`${charge.name}-${charge.charge_month}`} className="text-xs">
                {chargeLine(charge, fund.year_month, shown[index], held)}
              </li>
            ))}
          </ul>
        )}
      </td>
    </tr>
  )
}

/** Whether this entry hangs off one repeating charge rather than a category. */
function fillsForOneCharge(fund: FundStatus): boolean {
  return fund.recurring_id !== null
}

/**
 * What the button that removes an entry says it does.
 *
 * A category fund is deleted; a charge fund is *unmarked*, which is the word
 * the owner used to create it. Naming it "eliminar" would suggest the charge
 * goes with it, and nothing about the charge changes.
 */
function removalLabel(fund: FundStatus, shape: FundShape): string {
  return fillsForOneCharge(fund)
    ? `Dejar de juntar para ${fund.name}`
    : `Eliminar el ${shape} de ${fund.name}`
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
    <>
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
        <td className="px-3 py-2 text-right align-top tabular-nums">
          {formatCents(fund.asks, fund.currency)}
        </td>
        <td className="px-3 py-2 text-right align-top tabular-nums">
          {formatCents(fund.holds, fund.currency)}
        </td>
        <td className="px-3 py-2 align-top">
          <StatusBadge kind="onTrack" value={fund.on_track} />
        </td>
        <td className="px-3 py-2 text-right align-top">
          <Button
            variant="ghost"
            size="sm"
            aria-label={removalLabel(fund, shape)}
            onClick={onDelete}
          >
            {fillsForOneCharge(fund) ? "Dejar de juntar" : "Eliminar"}
          </Button>
        </td>
      </tr>
      <FundCharges fund={fund} />
    </>
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
    <Section label={heading} says={says} headingId={headingId}>
      {funds.length === 0 ? (
        <p className="max-w-prose py-2 text-sm" style={{ color: "var(--muted-foreground)" }}>
          {`Todavía no tienes ${shape}s. ${shapeSentence(shape)}.`}
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table aria-labelledby={headingId} className="w-full text-sm">
            <thead>
              <tr style={{ color: "var(--muted-foreground)" }}>
                {COLUMNS.map((column) => (
                  <th
                    key={column.label}
                    className={`px-3 pb-2 ${column.align} text-xs font-medium uppercase tracking-wide`}
                  >
                    {column.label}
                  </th>
                ))}
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
    </Section>
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
      toast.success(
        fillsForOneCharge(fund)
          ? `Dejaste de juntar para ${fund.name}`
          : `${nounOf(shapeOf(fund))} eliminado`,
      )
      invalidate(qc, "fundWrite")
      setDeleting(null)
    },
    onError: (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error"),
  })

  const deletingShape = deleting === null ? "fondo" : shapeOf(deleting)
  const unmarking = deleting !== null && fillsForOneCharge(deleting)

  return (
    <div className="space-y-10">
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
          <div className="space-y-10">
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
        title={unmarking ? "Dejar de juntar" : `Eliminar ${deletingShape}`}
        description={
          unmarking
            ? `Dejas de juntar para "${deleting?.name}". El cobro sigue igual y ningún movimiento cambia, pero lo que llevas juntado se pierde.`
            : `Se elimina el ${deletingShape} de "${deleting?.name}". La categoría y sus movimientos no cambian.`
        }
        confirmLabel={unmarking ? "Dejar de juntar" : "Eliminar"}
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting)}
      />
    </div>
  )
}
