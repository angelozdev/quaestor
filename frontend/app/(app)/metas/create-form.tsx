"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { MoneyInput } from "@/components/money-input"
import { createMeta, previewMeta } from "@/lib/api/metas"
import type { MetaCreate } from "@/lib/api/types"
import { ApiError } from "@/lib/api/types"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Button, Input, Label } from "@/ui"

/** What the form knows before it is complete enough to ask the server anything. */
function askable(name: string, amount: number | null, targetMonth: string): MetaCreate | null {
  const dated = /^\d{4}-\d{2}$/.test(targetMonth)
  return name.trim() === "" || amount === null || !dated
    ? null
    : { name: name.trim(), amount, target_month: targetMonth }
}

export function CreateMetaForm({ month, onDone }: { month: string; onDone: () => void }) {
  const [name, setName] = useState("")
  const [amount, setAmount] = useState<number | null>(null)
  const [targetMonth, setTargetMonth] = useState("")
  const queryClient = useQueryClient()

  const body = askable(name, amount, targetMonth)
  const preview = useQuery({
    queryKey: qk.metaPreview(body),
    queryFn: () => previewMeta(month, body as MetaCreate),
    enabled: body !== null,
  })

  const create = useMutation({
    mutationFn: () => createMeta(month, body as MetaCreate),
    onSuccess: async () => {
      toast.success("Meta creada.")
      await invalidate(queryClient, "metaWrite")
      onDone()
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "No se pudo crear la meta."),
  })

  const asks = preview.data?.asks ?? null
  const overTheMonth = preview.data?.over_the_month === true

  return (
    <form
      className="space-y-3 rounded-md border p-4"
      style={{ borderColor: "var(--border)" }}
      onSubmit={(event) => {
        event.preventDefault()
        if (body !== null) create.mutate()
      }}
    >
      <div className="space-y-1.5">
        <Label htmlFor="meta-name">Nombre *</Label>
        <Input id="meta-name" value={name} onChange={(e) => setName(e.target.value)} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="meta-amount">Cuánto * (COP)</Label>
        <MoneyInput id="meta-amount" currency="COP" value={amount} onChange={setAmount} />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="meta-month">Cuándo *</Label>
        <Input
          id="meta-month"
          type="month"
          value={targetMonth}
          onChange={(e) => setTargetMonth(e.target.value)}
        />
      </div>

      {asks !== null && (
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          Te pediría {formatCents(asks, "COP")} al mes.
        </p>
      )}
      {overTheMonth && (
        <p role="alert" className="text-sm" style={{ color: "var(--destructive)" }}>
          Es más de lo que tu mes tiene.
        </p>
      )}

      <div className="flex gap-2">
        <Button type="submit" disabled={body === null || create.isPending}>
          {overTheMonth ? "Crear de todos modos" : "Crear"}
        </Button>
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancelar
        </Button>
      </div>
    </form>
  )
}
