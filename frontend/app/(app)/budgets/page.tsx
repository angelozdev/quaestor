"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { useState } from "react"
import { toast } from "sonner"
import { EmptyState } from "@/components/empty-state"
import { MoneyInput } from "@/components/money-input"
import { PageHeader } from "@/components/page-header"
import { QueryBoundary } from "@/components/query-boundary"
import { SkeletonCard, SkeletonRows } from "@/components/skeleton"
import { assignBudget, listBudgets, safeToSpend } from "@/lib/api/budgets"
import { ApiError, applyApiErrorsToForm } from "@/lib/api/types"
import { formatDate } from "@/lib/date"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Button, Input } from "@/ui"
import { type AssignBudgetValues, assignBudgetSchema } from "./budgets.schema"

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 py-1.5">
      <span
        className="text-sm"
        style={{ color: strong ? "var(--foreground)" : "var(--muted-foreground)" }}
      >
        {label}
      </span>
      <span className={`tabular-nums ${strong ? "text-sm font-semibold" : "text-sm"}`}>
        {value}
      </span>
    </div>
  )
}

const defaultValues: AssignBudgetValues = {
  category: "",
  amount: Number.NaN,
  yearMonth: format(new Date(), "yyyy-MM"),
}

export default function BudgetsPage() {
  const [month, setMonth] = useState(format(new Date(), "yyyy-MM"))
  const qc = useQueryClient()
  const sts = useQuery({ queryKey: qk.safeToSpend(month), queryFn: () => safeToSpend(month) })
  const lines = useQuery({ queryKey: qk.budgets(month), queryFn: () => listBudgets(month) })

  const [editingCat, setEditingCat] = useState<number | null>(null)
  const assignForm = useTanStackForm({
    defaultValues,
    validators: { onChange: assignBudgetSchema },
    onSubmit: async ({ value }) => {
      assign.mutate(value)
    },
  })

  const assign = useMutation({
    mutationFn: (values: AssignBudgetValues) => {
      if (editingCat === null) throw new Error("editingCat is required")
      return assignBudget({
        category_id: editingCat,
        year_month: values.yearMonth,
        amount_assigned: values.amount,
      })
    },
    onSuccess: () => {
      toast.success("Sobre asignado")
      invalidate(qc, "budgetWrite")
      setEditingCat(null)
      assignForm.reset(defaultValues)
    },
    onError: (e: unknown) => {
      applyApiErrorsToForm(assignForm, e)
      toast.error(e instanceof ApiError ? e.message : "Error")
    },
  })

  return (
    <div className="space-y-6">
      <PageHeader
        title="Presupuestos"
        subtitle={month}
        action={
          <Input
            type="month"
            value={month}
            onChange={(e) => setMonth(e.target.value)}
            className="w-40"
          />
        }
      />

      <QueryBoundary
        query={sts}
        skeleton={<SkeletonCard />}
        errorMessage="No se pudo cargar disponible para gastar"
      >
        {(data) => (
          <div
            className="space-y-4 rounded-lg border p-5"
            style={{ borderColor: "var(--border)", background: "var(--card)" }}
          >
            <div>
              <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                Disponible para gastar
              </p>
              <p className="text-4xl font-bold tabular-nums tracking-tight">
                {formatCents(data.free, "COP")}
              </p>
            </div>
            <hr style={{ borderColor: "var(--border)" }} />
            <div>
              <Row label="Ingreso previsto" value={formatCents(data.income_forecast, "COP")} />
              <Row label="Comprometido" value={formatCents(data.committed, "COP")} />
              <Row label="Asignado a sobres" value={formatCents(data.assigned_envelopes, "COP")} />
              <Row label="Libre" value={formatCents(data.free, "COP")} strong />
            </div>
            {data.committed_breakdown.length > 0 && (
              <>
                <hr style={{ borderColor: "var(--border)" }} />
                <div className="space-y-1">
                  <p
                    className="text-xs font-medium uppercase tracking-wider"
                    style={{ color: "var(--muted-foreground)" }}
                  >
                    Comprometido
                  </p>
                  {data.committed_breakdown.map((c) => (
                    <Row
                      key={`${c.kind}-${c.name}-${c.date}-${c.amount}`}
                      label={`${c.name} · ${formatDate(c.date)}`}
                      value={formatCents(c.amount, "COP")}
                    />
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </QueryBoundary>

      <QueryBoundary
        query={lines}
        skeleton={<SkeletonRows rows={6} />}
        errorMessage="No se pudieron cargar los sobres"
        empty={{
          when: (rows) => rows.length === 0,
          node: <EmptyState message="Aún no hay sobres este mes" />,
        }}
      >
        {(rows) => (
          <div className="space-y-3">
            <h2 className="text-sm font-medium" style={{ color: "var(--muted-foreground)" }}>
              Sobres
            </h2>
            <div
              className="overflow-hidden rounded-lg border"
              style={{ borderColor: "var(--border)" }}
            >
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ color: "var(--muted-foreground)" }}>
                    <th className="px-3 py-2.5 text-left text-xs font-medium">Categoría</th>
                    <th className="px-3 py-2.5 text-right text-xs font-medium">Asignado</th>
                    <th className="px-3 py-2.5 text-right text-xs font-medium">Gastado</th>
                    <th className="px-3 py-2.5 text-right text-xs font-medium">Disponible</th>
                    <th className="w-32 px-3 py-2.5" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((l) => (
                    <tr
                      key={l.category_id}
                      className="border-t"
                      style={{ borderColor: "var(--border)" }}
                    >
                      <td className="px-3 py-2.5">{l.category_name}</td>
                      <td
                        className="px-3 py-2.5 text-right tabular-nums"
                        style={{ color: "var(--muted-foreground)" }}
                      >
                        {editingCat === l.category_id ? (
                          <assignForm.Field name="amount">
                            {(field) => {
                              const error = field.state.meta.errors[0]
                              const errorMessage =
                                typeof error === "string"
                                  ? error
                                  : error &&
                                      typeof error === "object" &&
                                      "message" in error &&
                                      typeof error.message === "string"
                                    ? error.message
                                    : error
                                      ? String(error)
                                      : null
                              return (
                                <div className="space-y-1">
                                  <MoneyInput
                                    currency="COP"
                                    value={
                                      typeof field.state.value === "number" &&
                                      Number.isFinite(field.state.value)
                                        ? (field.state.value as number)
                                        : null
                                    }
                                    onChange={(cents) =>
                                      field.handleChange((cents ?? Number.NaN) as never)
                                    }
                                  />
                                  {errorMessage && (
                                    <p className="text-xs text-destructive">{errorMessage}</p>
                                  )}
                                </div>
                              )
                            }}
                          </assignForm.Field>
                        ) : (
                          formatCents(l.assigned, "COP")
                        )}
                      </td>
                      <td
                        className="px-3 py-2.5 text-right tabular-nums"
                        style={{ color: "var(--muted-foreground)" }}
                      >
                        {formatCents(l.spent, "COP")}
                      </td>
                      <td
                        className="px-3 py-2.5 text-right tabular-nums font-medium"
                        style={{
                          color: l.status === "over" ? "var(--expense)" : "var(--income)",
                        }}
                      >
                        {formatCents(l.available, "COP")}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        {editingCat === l.category_id ? (
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              type="button"
                              onClick={() => {
                                setEditingCat(null)
                                assignForm.reset(defaultValues)
                              }}
                            >
                              Cancelar
                            </Button>
                            <Button
                              size="sm"
                              type="button"
                              disabled={assign.isPending}
                              onClick={() => void assignForm.handleSubmit()}
                            >
                              Guardar
                            </Button>
                          </div>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditingCat(l.category_id)
                              assignForm.reset({
                                category: String(l.category_id),
                                amount: l.assigned,
                                yearMonth: month,
                              })
                            }}
                          >
                            Asignar
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </QueryBoundary>
    </div>
  )
}
