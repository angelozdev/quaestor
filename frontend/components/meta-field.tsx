"use client"

import { useQuery } from "@tanstack/react-query"
import { listMetas } from "@/lib/api/metas"
import { qk } from "@/lib/query"
import { Label, Select } from "@/ui"

const NONE = "__none__"

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
  const metas = useQuery({
    queryKey: qk.metas(month),
    queryFn: () => listMetas(month),
  })

  const items = [
    { value: NONE, label: "Ninguna" },
    ...(metas.data ?? []).map((meta) => ({ value: String(meta.meta_id), label: meta.name })),
  ]

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>¿Es la compra de una meta?</Label>
      <Select
        id={id}
        value={value === null ? NONE : String(value)}
        onValueChange={(chosen) => onChange(!chosen || chosen === NONE ? null : Number(chosen))}
        items={items}
        placeholder={metas.isLoading ? "Cargando…" : "Ninguna"}
        disabled={metas.isLoading}
      />
      <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
        Si eliges una, esta compra la completa y deja de contar contra el fondo de su categoría.
      </p>
    </div>
  )
}
