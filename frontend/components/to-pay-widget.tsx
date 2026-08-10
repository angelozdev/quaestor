"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { endOfMonth, endOfWeek, format, startOfMonth, startOfWeek } from "date-fns"
import { useState } from "react"
import { toast } from "sonner"
import { ErrorState } from "@/components/error-state"
import { MoneyAmount } from "@/components/money-amount"
import { confirmPayment, toPay } from "@/lib/api/planned"
import type { Transaction } from "@/lib/api/types"
import { formatDate } from "@/lib/date"
import { formatCents } from "@/lib/money"
import { qk } from "@/lib/query"
import { Badge, Button } from "@/ui"

type Scope = "week" | "month"

function windowFor(scope: Scope) {
  const now = new Date()
  const [since, until] =
    scope === "week"
      ? [startOfWeek(now, { weekStartsOn: 1 }), endOfWeek(now, { weekStartsOn: 1 })]
      : [startOfMonth(now), endOfMonth(now)]
  return { since: format(since, "yyyy-MM-dd"), until: format(until, "yyyy-MM-dd") }
}

export function ToPayWidget() {
  const qc = useQueryClient()
  const [scope, setScope] = useState<Scope>("week")
  const { since, until } = windowFor(scope)

  const query = useQuery({
    queryKey: qk.toPay(since, until),
    queryFn: () => toPay(since, until),
  })

  const markPaid = useMutation({
    mutationFn: (id: number) => confirmPayment(id),
    onSuccess: () => {
      toast.success("Pago confirmado")
      qc.invalidateQueries({ queryKey: ["planned"] })
      qc.invalidateQueries({ queryKey: ["reports"] })
      qc.invalidateQueries({ queryKey: ["accounts"] })
      qc.invalidateQueries({ queryKey: ["funds"] })
    },
    onError: (e: unknown) =>
      toast.error(e instanceof Error ? e.message : "No se pudo confirmar el pago"),
  })

  return (
    <div className="space-y-3">
      {/* Header */}
      <div
        className="flex items-center justify-between gap-4 border-b pb-2"
        style={{ borderColor: "var(--border)" }}
      >
        <h2 className="text-xs font-medium" style={{ color: "var(--muted-foreground)" }}>
          Por pagar
        </h2>
        <div
          className="flex items-center gap-1 rounded-md p-0.5"
          style={{ background: "var(--muted)" }}
        >
          {(["week", "month"] as Scope[]).map((s) => {
            const active = scope === s
            return (
              <Button
                key={s}
                type="button"
                size="xs"
                variant={active ? "outline" : "ghost"}
                onClick={() => setScope(s)}
                className={active ? "rounded" : "rounded text-muted-foreground"}
              >
                {s === "week" ? "Esta semana" : "Este mes"}
              </Button>
            )
          })}
        </div>
      </div>

      {query.isLoading && (
        <div className="space-y-2">
          {[1, 2].map((i) => (
            <div
              key={i}
              className="h-11 rounded animate-pulse"
              style={{ background: "var(--muted)" }}
            />
          ))}
        </div>
      )}

      {query.isError && (
        <ErrorState message="No se pudo cargar lo pendiente" onRetry={() => query.refetch()} />
      )}

      {query.data && (
        <>
          <p className="text-xl font-semibold tabular-nums tracking-tight">
            {formatCents(query.data.total_base, "COP")}
          </p>

          {query.data.overdue.length === 0 && query.data.upcoming.length === 0 ? (
            <p className="text-sm py-1" style={{ color: "var(--muted-foreground)" }}>
              Nada pendiente
            </p>
          ) : (
            <div className="space-y-4">
              {query.data.overdue.length > 0 && (
                <section className="space-y-0">
                  <header className="flex items-center gap-2 pb-1">
                    <p className="text-xs font-medium" style={{ color: "var(--expense)" }}>
                      Vencidos
                    </p>
                    <Badge variant="destructive">{query.data.overdue.length}</Badge>
                  </header>
                  <ul className="space-y-0">
                    {query.data.overdue.map((item) => (
                      <OverdueRow
                        key={item.id}
                        item={item}
                        pending={markPaid.isPending}
                        onMarkPaid={() => markPaid.mutate(item.id)}
                      />
                    ))}
                  </ul>
                </section>
              )}

              {query.data.upcoming.length > 0 && (
                <section className="space-y-0">
                  <header className="pb-1">
                    <h2
                      className="text-xs font-medium"
                      style={{ color: "var(--muted-foreground)" }}
                    >
                      {scope === "week" ? "Esta semana" : "Este mes"}
                    </h2>
                  </header>
                  <ul className="space-y-0">
                    {query.data.upcoming.map((item) => (
                      <UpcomingRow
                        key={item.id}
                        item={item}
                        pending={markPaid.isPending}
                        onMarkPaid={() => markPaid.mutate(item.id)}
                      />
                    ))}
                  </ul>
                </section>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

/**
 * Row for a planned transaction past its due date. Wraps `ToPayRow` with
 * the destructive "Vencido" badge and destructive due-date color.
 */
function OverdueRow({
  item,
  pending,
  onMarkPaid,
}: {
  item: Transaction
  pending: boolean
  onMarkPaid: () => void
}) {
  return (
    <ToPayRow
      item={item}
      pending={pending}
      onMarkPaid={onMarkPaid}
      badge={<Badge variant="destructive">Vencido</Badge>}
      dateColor="var(--destructive)"
    />
  )
}

/**
 * Row for a planned transaction still due within the active scope window.
 * No badge is rendered; the due date uses the muted foreground color.
 */
function UpcomingRow({
  item,
  pending,
  onMarkPaid,
}: {
  item: Transaction
  pending: boolean
  onMarkPaid: () => void
}) {
  return (
    <ToPayRow
      item={item}
      pending={pending}
      onMarkPaid={onMarkPaid}
      dateColor="var(--muted-foreground)"
    />
  )
}

/**
 * Shared row layout for a single planned transaction. `badge` is rendered
 * next to the payee when present (overdue rows); `dateColor` controls the
 * due-date text color so the row can signal its state visually.
 */
function ToPayRow({
  item,
  pending,
  onMarkPaid,
  badge,
  dateColor,
}: {
  item: Transaction
  pending: boolean
  onMarkPaid: () => void
  badge?: React.ReactNode
  dateColor: string
}) {
  return (
    <li
      className="flex items-center justify-between py-2.5 border-t gap-4"
      style={{ borderColor: "var(--border)" }}
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <p className="text-sm font-medium truncate">{item.payee}</p>
          {badge}
        </div>
        <time dateTime={item.date} className="text-xs" style={{ color: dateColor }}>
          {formatDate(item.date)}
        </time>
      </div>
      <div className="flex items-center gap-4 shrink-0">
        <MoneyAmount cents={item.amount} currency={item.currency} className="text-sm font-medium" />
        <Button type="button" size="sm" variant="outline" disabled={pending} onClick={onMarkPaid}>
          Marcar pagado
        </Button>
      </div>
    </li>
  )
}
