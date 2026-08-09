"use client"

import { EntitySelect } from "@/components/entity-select"
import { listMetas } from "@/lib/api/metas"
import { qk } from "@/lib/query"
import { Label } from "@/ui"

/**
 * The metas of one month, shaped for a picker.
 *
 * Its own cache entry under the metas root: the month's list is cached as
 * `MetaStatus[]` for the screen that reads holdings and progress, and two
 * shapes under one key would hand whichever mounted second the wrong one.
 * Both still answer to a `metaWrite` invalidation, which matches by prefix.
 */
const metaOptions = (month: string) => ({
  queryKey: [...qk.metas(month), "options"] as const,
  queryFn: async () =>
    (await listMetas(month)).map((meta) => ({ id: meta.meta_id, name: meta.name })),
})

/**
 * Point a purchase at one of the metas running in the month it happened.
 *
 * The offering comes from the month's own list, which carries no meta the
 * owner cancelled — a cancelled meta takes no new link, and the screen never
 * offers what the server would refuse (AC-25).
 */
export function MetaField({
  id,
  month,
  value,
  onChange,
}: {
  id: string
  month: string
  value: number | null
  onChange: (metaId: number | null) => void
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>¿Es la compra de una meta?</Label>
      <EntitySelect
        id={id}
        value={value}
        onChange={onChange}
        allowNullLabel="Ninguna"
        placeholder="Ninguna"
        {...metaOptions(month)}
      />
      <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
        Si eliges una, esta compra la completa y deja de contar contra el fondo de su categoría.
      </p>
    </div>
  )
}
