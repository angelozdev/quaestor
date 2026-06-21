"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { useState } from "react"
import { Controller, useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"
import { ErrorState } from "@/components/error-state"
import { MoneyInput } from "@/components/money-input"
import { PageHeader } from "@/components/page-header"
import { assignBudget, listBudgets, safeToSpend } from "@/lib/api/budgets"
import { ApiError } from "@/lib/api/types"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { positiveCents } from "@/lib/schemas/primitives"
import { Button, Input } from "@/ui"

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

const assignBudgetSchema = z.object({
  amount: positiveCents,
  yearMonth: z.string().regex(/^\d{4}-\d{2}$/, "Mes inválido"),
})

type AssignBudgetValues = z.infer<typeof assignBudgetSchema>

export default function BudgetsPage() {
  const [month, setMonth] = useState(format(new Date(), "yyyy-MM"))
  const qc = useQueryClient()
  const sts = useQuery({ queryKey: qk.safeToSpend(month), queryFn: () => safeToSpend(month) })
  const lines = useQuery({ queryKey: qk.budgets(month), queryFn: () => listBudgets(month) })

  const [editingCat, setEditingCat] = useState<number | null>(null)
  const assignForm = useForm<AssignBudgetValues>({
    resolver: zodResolver(assignBudgetSchema),
    defaultValues: {
      amount: Number.NaN,
      yearMonth: format(new Date(), "yyyy-MM"),
    },
  })
  const { reset: resetAssign } = assignForm

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
      resetAssign({
        amount: Number.NaN,
        yearMonth: format(new Date(), "yyyy-MM"),
      })
    },
    onError: (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error"),
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

      {sts.isError && (
        <ErrorState
          message="No se pudo cargar disponible para gastar"
          onRetry={() => sts.refetch()}
        />
      )}

      {sts.data && (
        <div
          className="space-y-4 rounded-lg border p-5"
          style={{ borderColor: "var(--border)", background: "var(--card)" }}
        >
          <div>
            <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
              Disponible para gastar
            </p>
            <p className="text-4xl font-bold tabular-nums tracking-tight">
              {formatCents(sts.data.free, "COP")}
            </p>
          </div>
          <hr style={{ borderColor: "var(--border)" }} />
          <div>
            <Row label="Ingreso previsto" value={formatCents(sts.data.income_forecast, "COP")} />
            <Row label="Comprometido" value={formatCents(sts.data.committed, "COP")} />
            <Row
              label="Asignado a sobres"
              value={formatCents(sts.data.assigned_envelopes, "COP")}
            />
            <Row label="Libre" value={formatCents(sts.data.free, "COP")} strong />
          </div>
          {sts.data.committed_breakdown.length > 0 && (
            <>
              <hr style={{ borderColor: "var(--border)" }} />
              <div className="space-y-1">
                <p
                  className="text-xs font-medium uppercase tracking-wider"
                  style={{ color: "var(--muted-foreground)" }}
                >
                  Comprometido
                </p>
                {sts.data.committed_breakdown.map((c) => (
                  <Row
                    key={`${c.kind}-${c.name}-${c.date}-${c.amount}`}
                    label={`${c.name} · ${c.date}`}
                    value={formatCents(c.amount, "COP")}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {lines.data && lines.data.length > 0 && (
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
                {lines.data.map((l) => (
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
                        <Controller
                          control={assignForm.control}
                          name="amount"
                          render={({ field, fieldState: { error } }) => (
                            <div className="space-y-1">
                              <MoneyInput
                                currency="COP"
                                value={
                                  typeof field.value === "number" && Number.isFinite(field.value)
                                    ? field.value
                                    : null
                                }
                                onChange={(cents) => field.onChange(cents ?? Number.NaN)}
                              />
                              {error?.message && (
                                <p className="text-xs text-destructive">{error.message}</p>
                              )}
                            </div>
                          )}
                        />
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
                      style={{ color: l.status === "over" ? "var(--expense)" : "var(--income)" }}
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
                              resetAssign({
                                amount: Number.NaN,
                                yearMonth: format(new Date(), "yyyy-MM"),
                              })
                            }}
                          >
                            Cancelar
                          </Button>
                          <Button
                            size="sm"
                            type="button"
                            disabled={assign.isPending}
                            onClick={assignForm.handleSubmit((values) => assign.mutate(values))}
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
                            resetAssign({
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
    </div>
  )
}
