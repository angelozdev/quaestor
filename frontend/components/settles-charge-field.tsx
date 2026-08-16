"use client"

import { useQuery } from "@tanstack/react-query"
import { format, parseISO } from "date-fns"
import { es } from "date-fns/locale"
import { useEffect } from "react"
import { EntitySelect } from "@/components/entity-select"
import { chargeMarks, openTurns } from "@/lib/api/funds"
import { qk } from "@/lib/query"
import { Label } from "@/ui"

/**
 * The charges of one category that are being saved for, shaped for a picker.
 *
 * Only the marked ones are offered, and that is the whole point: a fund that
 * fills for a charge is the only thing a link can settle, so offering an
 * unmarked charge would promise something nothing acts on.
 *
 * The category is in the key because it is in the answer — the narrowing
 * happens here rather than at the caller, so the entry cached under this key
 * is the list it says it is. One query serves both the decision to show the
 * field and the picker inside it; the second `useQuery` shares this entry
 * instead of minting a parallel one that goes stale on its own.
 */
const settleOptions = (month: string, categoryId: number | null) => ({
  queryKey: [...qk.chargeMarks(month), "settle", categoryId ?? "none"] as const,
  queryFn: async () =>
    (await chargeMarks(month))
      .filter((mark) => mark.fund_id !== null && mark.category_id === categoryId)
      .map((mark) => ({ id: mark.recurring_id, name: mark.name })),
})

const turnOptions = (recurringId: number | null) => ({
  queryKey: qk.openTurns(recurringId),
  queryFn: async () => (recurringId === null ? [] : await openTurns(recurringId)),
  enabled: recurringId !== null,
})

/** "5 de noviembre de 2026" — the way the owner reads a date everywhere else. */
function readable(due: string): string {
  return format(parseISO(due), "d 'de' MMMM 'de' yyyy", { locale: es })
}

/**
 * One array for "no turns yet", shared.
 *
 * `turns.data ?? []` builds a new array on every render, and an array identity
 * that changes every render is a dependency that changes every render — which
 * is how the effect below ends up calling itself until React stops it.
 */
const NONE: readonly string[] = []

/**
 * Say which repeating charge this payment settled, and which of its turns.
 *
 * The link is what settles, never the amount: a payment of exactly what the
 * insurance costs is not the insurance unless the owner says so, and guessing
 * by amount would empty the fund the day a fire extinguisher costs the same.
 *
 * The turn is asked only when there is a choice to make. One turn open is the
 * ordinary case — the bill that just arrived — and the field answers it without
 * a question; more than one means the owner is paying a specific bill and only
 * he knows which (ADR-0058). Either way a turn is always sent, because a
 * payment that names no turn is the month-at-a-time reading this replaced.
 *
 * A category with nothing marked offers nothing — there is no cycle to close,
 * so the field stays out of the form rather than showing an empty picker.
 */
export function SettlesChargeField({
  id,
  month,
  categoryId,
  value,
  settlesDue,
  onChange,
  onTurnChange,
}: {
  id: string
  month: string
  categoryId: number | null
  value: number | null
  settlesDue: string | null
  onChange: (recurringId: number | null) => void
  onTurnChange: (due: string | null) => void
}) {
  const options = useQuery(settleOptions(month, categoryId))
  const turns = useQuery(turnOptions(value))
  const open = turns.data ?? NONE

  useEffect(() => {
    if (value === null) {
      if (settlesDue !== null) onTurnChange(null)
      return
    }
    if (open.length > 0 && (settlesDue === null || !open.includes(settlesDue))) {
      onTurnChange(open[0])
    }
  }, [value, open, settlesDue, onTurnChange])

  if ((options.data ?? []).length === 0) return null
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>¿Este pago salda un cobro?</Label>
      <EntitySelect
        id={id}
        value={value}
        onChange={onChange}
        allowNullLabel="Ninguno, es un gasto aparte"
        placeholder="Ninguno, es un gasto aparte"
        {...settleOptions(month, categoryId)}
      />
      {value !== null && open.length > 1 && (
        <div className="space-y-1.5 pt-1.5">
          <Label htmlFor={`${id}-turn`}>¿Cuál vencimiento?</Label>
          <EntitySelect
            id={`${id}-turn`}
            value={open.indexOf(settlesDue ?? open[0])}
            onChange={(chosen) => onTurnChange(chosen === null ? null : open[chosen])}
            placeholder="Elige el vencimiento"
            queryKey={[...qk.openTurns(value), "labels"] as const}
            queryFn={async () => open.map((due, at) => ({ id: at, name: readable(due) }))}
          />
        </div>
      )}
      <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
        Si eliges uno, su caja se vacía y empieza a juntar para el cobro siguiente.
      </p>
    </div>
  )
}
