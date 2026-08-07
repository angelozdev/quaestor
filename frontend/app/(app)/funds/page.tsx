"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { useState } from "react"
import { toast } from "sonner"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState } from "@/components/empty-state"
import { PageHeader } from "@/components/page-header"
import { QueryBoundary } from "@/components/query-boundary"
import { SkeletonRows } from "@/components/skeleton"
import { StatusBadge } from "@/components/status-badge"
import { deleteFund, listFunds, moneyAvailable } from "@/lib/api/funds"
import type { FundStatus } from "@/lib/api/types"
import { ApiError } from "@/lib/api/types"
import { monthNameOf, nextYearMonth } from "@/lib/date"
import { type FundShape, nounOf, shapeOf } from "@/lib/funds"
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

const NOTHING_YET = (
  <>
    <p>
      Un <strong>fondo</strong> aparta plata cada mes y guarda lo que sobra — para el mantenimiento
      del carro, o para pagar una suscripción anual mes a mes.
    </p>
    <p>
      Un <strong>presupuesto</strong> es un tope: lo que no gastes no se guarda.
    </p>
  </>
)

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
    <tr className="border-t" style={{ borderColor: "var(--border)" }}>
      <td className="px-3 py-2.5 align-top">
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
      <td className="px-3 py-2.5 align-top" style={{ color: "var(--muted-foreground)" }}>
        {ruleLabel(fund.rule, shape)}
      </td>
      <td className="px-3 py-2.5 text-right align-top tabular-nums">
        {formatCents(fund.asks, "COP")}
      </td>
      <td className="px-3 py-2.5 text-right align-top tabular-nums">
        {formatCents(fund.holds, "COP")}
      </td>
      <td className="px-3 py-2.5 align-top">
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
      <h2 id={headingId} className="text-xs font-semibold tracking-wider">
        {heading}
      </h2>
      <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
        {says}
      </p>
      <div className="overflow-hidden rounded-lg border" style={{ borderColor: "var(--border)" }}>
        <table aria-labelledby={headingId} className="w-full text-sm">
          <thead>
            <tr style={{ color: "var(--muted-foreground)" }}>
              <th className="px-3 py-2.5 text-left text-xs font-medium">Categoría</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium">Regla</th>
              <th className="px-3 py-2.5 text-right text-xs font-medium">Pide</th>
              <th className="px-3 py-2.5 text-right text-xs font-medium">Tiene</th>
              <th className="px-3 py-2.5 text-left text-xs font-medium">Estado</th>
              <th className="w-28 px-3 py-2.5" />
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
              action={{ label: "Crear el primero", onClick: () => setMaking("fondo") }}
            />
          ),
        }}
      >
        {(data) => (
          <div className="space-y-8">
            {SECTIONS.map((section) => {
              const funds = data.funds.filter((fund) => shapeOf(fund) === section.shape)
              if (funds.length === 0) return null
              return (
                <FundSection
                  key={section.shape}
                  shape={section.shape}
                  heading={section.heading}
                  says={section.says}
                  funds={funds}
                  startMonths={startMonths}
                  month={month}
                  onDelete={setDeleting}
                />
              )
            })}
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
