"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { format } from "date-fns"
import { useState } from "react"
import { toast } from "sonner"
import { ErrorState } from "@/components/error-state"
import { MoneyInput } from "@/components/money-input"
import { PageHeader } from "@/components/page-header"
import { assignBudget, listBudgets, safeToSpend } from "@/lib/api/budgets"
import { ApiError } from "@/lib/api/types"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
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

export default function BudgetsPage() {
  const [month, setMonth] = useState(format(new Date(), "yyyy-MM"))
  const qc = useQueryClient()
  const sts = useQuery({ queryKey: qk.safeToSpend(month), queryFn: () => safeToSpend(month) })
  const lines = useQuery({ queryKey: qk.budgets(month), queryFn: () => listBudgets(month) })

  const [editingCat, setEditingCat] = useState<number | null>(null)
  const [draft, setDraft] = useState<number | null>(null)
  const assign = useMutation({
    mutationFn: (categoryId: number) =>
      assignBudget({ category_id: categoryId, year_month: month, amount_assigned: draft ?? 0 }),
    onSuccess: () => {
      toast.success("Sobre asignado")
      invalidate(qc, "budgetWrite")
      setEditingCat(null)
      setDraft(null)
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
                        <MoneyInput currency="COP" value={draft} onChange={setDraft} />
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
                            onClick={() => {
                              setEditingCat(null)
                              setDraft(null)
                            }}
                          >
                            Cancelar
                          </Button>
                          <Button
                            size="sm"
                            disabled={assign.isPending}
                            onClick={() => assign.mutate(l.category_id)}
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
                            setDraft(l.assigned)
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
