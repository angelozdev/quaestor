"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { listArchived, restoreMeta } from "@/lib/api/metas"
import { ApiError } from "@/lib/api/types"
import { monthNameOf } from "@/lib/date"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Button } from "@/ui"

/**
 * The metas the owner cancelled, and the way back.
 *
 * A restored meta starts again from nothing — cancelling already handed back
 * everything it held, and resuming with the old holdings would hand it over
 * twice (AC-29) — so the row says so before the owner clicks.
 */
export function ArchivedMetas({ month }: { month: string }) {
  const queryClient = useQueryClient()
  const archived = useQuery({ queryKey: qk.metasArchived(), queryFn: () => listArchived() })

  const restore = useMutation({
    mutationFn: (id: number) => restoreMeta(id, month),
    onSuccess: async () => {
      toast.success("La meta volvió, empezando desde cero.")
      await invalidate(queryClient, "metaWrite")
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : "No se pudo traerla de vuelta."),
  })

  if (archived.data === undefined || archived.data.length === 0) return null

  return (
    <section className="space-y-2">
      <h2 className="text-sm font-medium" style={{ color: "var(--muted-foreground)" }}>
        Canceladas
      </h2>
      <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
        Si traes una de vuelta, empieza otra vez desde cero: lo que tenía guardado ya volvió a tu
        bolsillo el mes que la cancelaste.
      </p>
      <ul className="space-y-2">
        {archived.data.map((meta) => (
          <li
            key={meta.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-3"
            style={{ borderColor: "var(--border)" }}
          >
            <span className="text-sm" style={{ color: "var(--muted-foreground)" }}>
              {meta.name} · quería {formatCents(meta.amount, meta.currency)} para{" "}
              {monthNameOf(meta.target_month)} {meta.target_month.slice(0, 4)}
            </span>
            <Button
              variant="ghost"
              size="sm"
              disabled={restore.isPending}
              onClick={() => restore.mutate(meta.id)}
            >
              Traer {meta.name} de vuelta
            </Button>
          </li>
        ))}
      </ul>
    </section>
  )
}
