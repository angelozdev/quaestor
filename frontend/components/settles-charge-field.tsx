"use client"

import { useQuery } from "@tanstack/react-query"
import { EntitySelect } from "@/components/entity-select"
import { chargeMarks } from "@/lib/api/funds"
import { qk } from "@/lib/query"
import { Label } from "@/ui"

/**
 * The charges of one category that are being saved for, shaped for a picker.
 *
 * Only the marked ones are offered, and that is the whole point: a fund that
 * fills for a charge is the only thing a link can settle, so offering an
 * unmarked charge would promise something nothing acts on.
 */
const settleOptions = (month: string, categoryId: number | null) => ({
  queryKey: [...qk.chargeMarks(month), "settle", categoryId ?? "none"] as const,
  queryFn: async () => (await chargeMarks(month)).filter((mark) => mark.fund_id !== null),
})

/**
 * Say which repeating charge this payment settled.
 *
 * The link is what settles, never the amount: a payment of exactly what the
 * insurance costs is not the insurance unless the owner says so, and guessing
 * by amount would empty the fund the day a fire extinguisher costs the same.
 *
 * A category with nothing marked offers nothing — there is no cycle to close,
 * so the field stays out of the form rather than showing an empty picker.
 */
export function SettlesChargeField({
  id,
  month,
  categoryId,
  value,
  onChange,
}: {
  id: string
  month: string
  categoryId: number | null
  value: number | null
  onChange: (recurringId: number | null) => void
}) {
  const options = useQuery(settleOptions(month, categoryId))
  const offered = (options.data ?? []).filter((mark) => mark.category_id === categoryId)
  if (offered.length === 0) return null
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>¿Este pago salda un cobro?</Label>
      <EntitySelect
        id={id}
        value={value}
        onChange={onChange}
        allowNullLabel="Ninguno, es un gasto aparte"
        placeholder="Ninguno, es un gasto aparte"
        queryKey={[...settleOptions(month, categoryId).queryKey, "select"] as const}
        queryFn={async () => offered.map((mark) => ({ id: mark.recurring_id, name: mark.name }))}
      />
      <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
        Si eliges uno, su caja se vacía y empieza a juntar para el cobro siguiente.
      </p>
    </div>
  )
}
