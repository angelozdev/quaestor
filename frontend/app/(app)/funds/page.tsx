"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { useState } from "react"
import { toast } from "sonner"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { EmptyState } from "@/components/empty-state"
import { EntitySelect } from "@/components/entity-select"
import { MoneyInput } from "@/components/money-input"
import { PageHeader } from "@/components/page-header"
import { QueryBoundary } from "@/components/query-boundary"
import { SkeletonRows } from "@/components/skeleton"
import { StatusBadge } from "@/components/status-badge"
import { listCategories } from "@/lib/api/categories"
import { createFund, deleteFund, moneyAvailable, previewFund } from "@/lib/api/funds"
import type { FundCreate, FundStatus } from "@/lib/api/types"
import { ApiError, applyApiErrorsToForm } from "@/lib/api/types"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Button, Checkbox, Input, Label, Select } from "@/ui"
import { type CreateFundValues, createFundSchema } from "./funds.schema"

const RULE_ITEMS = [
  { value: "fixed", label: "Monto fijo" },
  { value: "average", label: "Promedio de los últimos meses" },
  { value: "from-recurring", label: "Lo que piden sus obligaciones" },
  { value: "target-by-date", label: "Meta con fecha" },
]
const RULE_LABEL: Record<string, string> = Object.fromEntries(
  RULE_ITEMS.map((r) => [r.value, r.label]),
)

/** Only these two rules leave the choice open: a dated fund always accumulates. */
const RULES_THAT_CHOOSE = ["fixed", "average"]

function defaults(month: string): CreateFundValues {
  return {
    categoryId: null,
    rule: "fixed",
    startMonth: month,
    accumulates: true,
    amount: null,
    windowMonths: null,
    targetAmount: null,
    targetMonth: "",
  }
}

function bodyOf(values: CreateFundValues): FundCreate {
  const body: FundCreate = {
    category_id: values.categoryId as number,
    rule: values.rule,
    start_month: values.startMonth,
  }
  if (values.rule === "fixed") body.amount = values.amount
  if (values.rule === "average") body.window_months = values.windowMonths
  if (values.rule === "target-by-date") {
    body.target_amount = values.targetAmount
    body.target_month = values.targetMonth
  }
  if (RULES_THAT_CHOOSE.includes(values.rule)) body.accumulates = values.accumulates
  return body
}

export default function FundsPage() {
  const [month, setMonth] = useState(format(new Date(), "yyyy-MM"))
  const [creating, setCreating] = useState(false)
  const [warning, setWarning] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<FundStatus | null>(null)
  const qc = useQueryClient()

  const view = useQuery({
    queryKey: qk.moneyAvailable(month),
    queryFn: () => moneyAvailable(month),
  })

  const form = useTanStackForm({
    defaultValues: defaults(month),
    validators: { onChange: createFundSchema },
    onSubmit: async ({ value }) => {
      if (warning === null) ask.mutate(value)
      else create.mutate(value)
    },
  })

  const onErr = (form_: unknown) => (e: unknown) => {
    applyApiErrorsToForm(form_, e)
    toast.error(e instanceof ApiError ? e.message : "Error")
  }

  const ask = useMutation({
    mutationFn: (values: CreateFundValues) => previewFund(bodyOf(values)),
    onSuccess: (preview, values) => {
      if (preview.warning === null) create.mutate(values)
      else setWarning(preview.warning)
    },
    onError: onErr(form),
  })

  const create = useMutation({
    mutationFn: (values: CreateFundValues) => createFund(bodyOf(values)),
    onSuccess: () => {
      toast.success("Fondo creado")
      invalidate(qc, "fundWrite")
      setCreating(false)
      setWarning(null)
      form.reset(defaults(month))
    },
    onError: onErr(form),
  })

  const remove = useMutation({
    mutationFn: (fundId: number) => deleteFund(fundId),
    onSuccess: () => {
      toast.success("Fondo eliminado")
      invalidate(qc, "fundWrite")
      setDeleting(null)
    },
    onError: onErr(form),
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Fondos"
        subtitle={month}
        action={
          <div className="flex items-center gap-2">
            <Input
              type="month"
              aria-label="Mes"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className="w-40"
            />
            <Button
              onClick={() => {
                setWarning(null)
                form.reset(defaults(month))
                setCreating(true)
              }}
            >
              Nuevo fondo
            </Button>
          </div>
        }
      />

      {creating && (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            e.stopPropagation()
            void form.handleSubmit()
          }}
          className="space-y-4 rounded-lg border p-5"
          style={{ borderColor: "var(--border)", background: "var(--card)" }}
        >
          <form.Field name="categoryId">
            {(field) => (
              <div className="space-y-1.5">
                <Label htmlFor="fund-category">Categoría *</Label>
                <EntitySelect
                  id="fund-category"
                  value={field.state.value}
                  onChange={(v) => field.handleChange(v)}
                  queryKey={qk.categories(false, false)}
                  queryFn={() => listCategories(false, false)}
                />
              </div>
            )}
          </form.Field>

          <form.Field name="rule">
            {(field) => (
              <div className="space-y-1.5">
                <Label htmlFor="fund-rule">Regla *</Label>
                <Select
                  id="fund-rule"
                  value={field.state.value}
                  onValueChange={(v) => {
                    if (!v) return
                    field.handleChange(v as CreateFundValues["rule"])
                    setWarning(null)
                  }}
                  items={RULE_ITEMS}
                />
              </div>
            )}
          </form.Field>

          <form.Subscribe selector={(state) => state.values.rule}>
            {(rule) => (
              <>
                {rule === "fixed" && (
                  <form.Field name="amount">
                    {(field) => (
                      <div className="space-y-1.5">
                        <Label htmlFor="fund-amount">Monto mensual * (COP)</Label>
                        <MoneyInput
                          id="fund-amount"
                          currency="COP"
                          value={field.state.value}
                          onChange={(cents) => field.handleChange(cents)}
                        />
                      </div>
                    )}
                  </form.Field>
                )}

                {rule === "average" && (
                  <form.Field name="windowMonths">
                    {(field) => (
                      <div className="space-y-1.5">
                        <Label htmlFor="fund-window">Meses a promediar *</Label>
                        <Input
                          id="fund-window"
                          type="number"
                          min={1}
                          value={field.state.value === null ? "" : String(field.state.value)}
                          onChange={(e) =>
                            field.handleChange(
                              e.target.value === "" ? null : Number(e.target.value),
                            )
                          }
                        />
                      </div>
                    )}
                  </form.Field>
                )}

                {rule === "target-by-date" && (
                  <>
                    <form.Field name="targetAmount">
                      {(field) => (
                        <div className="space-y-1.5">
                          <Label htmlFor="fund-target">Objetivo * (COP)</Label>
                          <MoneyInput
                            id="fund-target"
                            currency="COP"
                            value={field.state.value}
                            onChange={(cents) => field.handleChange(cents)}
                          />
                        </div>
                      )}
                    </form.Field>
                    <form.Field name="targetMonth">
                      {(field) => (
                        <div className="space-y-1.5">
                          <Label htmlFor="fund-target-month">Mes objetivo *</Label>
                          <Input
                            id="fund-target-month"
                            type="month"
                            value={field.state.value}
                            onChange={(e) => field.handleChange(e.target.value)}
                          />
                        </div>
                      )}
                    </form.Field>
                  </>
                )}
              </>
            )}
          </form.Subscribe>

          <form.Field name="startMonth">
            {(field) => (
              <div className="space-y-1.5">
                <Label htmlFor="fund-start">Empieza en *</Label>
                <Input
                  id="fund-start"
                  type="month"
                  value={field.state.value}
                  onChange={(e) => field.handleChange(e.target.value)}
                />
              </div>
            )}
          </form.Field>

          <form.Subscribe selector={(state) => state.values.rule}>
            {(rule) =>
              RULES_THAT_CHOOSE.includes(rule) ? (
                <form.Field name="accumulates">
                  {(field) => (
                    <div className="flex items-center gap-2">
                      <Checkbox
                        id="fund-accumulates"
                        checked={field.state.value}
                        onCheckedChange={(c) => field.handleChange(Boolean(c))}
                      />
                      <Label htmlFor="fund-accumulates">Acumula lo que sobra cada mes</Label>
                    </div>
                  )}
                </form.Field>
              ) : null
            }
          </form.Subscribe>

          {warning !== null && (
            <p className="text-sm" style={{ color: "var(--destructive)" }} role="alert">
              {warning}
            </p>
          )}

          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setCreating(false)
                setWarning(null)
              }}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={ask.isPending || create.isPending}>
              {warning === null ? "Crear" : "Crear de todos modos"}
            </Button>
          </div>
        </form>
      )}

      <QueryBoundary
        query={view}
        skeleton={<SkeletonRows rows={5} />}
        errorMessage="No se pudieron cargar los fondos"
        empty={{
          when: (data) => data.funds.length === 0,
          node: <EmptyState message="Aún no hay fondos" />,
        }}
      >
        {(data) => (
          <div
            className="overflow-hidden rounded-lg border"
            style={{ borderColor: "var(--border)" }}
          >
            <table className="w-full text-sm">
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
                {data.funds.map((fund) => (
                  <tr
                    key={fund.fund_id}
                    className="border-t"
                    style={{ borderColor: "var(--border)" }}
                  >
                    <td className="px-3 py-2.5">{fund.name}</td>
                    <td className="px-3 py-2.5" style={{ color: "var(--muted-foreground)" }}>
                      {RULE_LABEL[fund.rule] ?? fund.rule}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {formatCents(fund.asks, "COP")}
                    </td>
                    <td className="px-3 py-2.5 text-right tabular-nums">
                      {formatCents(fund.holds, "COP")}
                    </td>
                    <td className="px-3 py-2.5">
                      <StatusBadge kind="onTrack" value={fund.on_track} />
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        aria-label={`Eliminar el fondo de ${fund.name}`}
                        onClick={() => setDeleting(fund)}
                      >
                        Eliminar
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryBoundary>

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Eliminar fondo"
        description={`Se elimina el fondo de "${deleting?.name}". La categoría y sus movimientos no cambian.`}
        confirmLabel="Eliminar"
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate(deleting.fund_id)}
      />
    </div>
  )
}
