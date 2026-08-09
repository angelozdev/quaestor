"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { MoneyInput } from "@/components/money-input"
import { createMeta, previewMeta } from "@/lib/api/metas"
import type { MetaCreate } from "@/lib/api/types"
import { ApiError, applyApiErrorsToForm } from "@/lib/api/types"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Button, Input, Label } from "@/ui"
import { type CreateMetaValues, createMetaSchema } from "./metas.schema"

const EMPTY: CreateMetaValues = { name: "", amount: Number.NaN, targetMonth: "" }

/** What the form knows before it is complete enough to ask the server anything. */
function askable(values: CreateMetaValues): MetaCreate | null {
  const parsed = createMetaSchema.safeParse(values)
  return parsed.success
    ? { name: parsed.data.name, amount: parsed.data.amount, target_month: parsed.data.targetMonth }
    : null
}

/**
 * What the meta would ask, asked of the server as soon as the form can say.
 *
 * Its own component because the answer depends on every field at once, and a
 * form isolates each field's renders from the others (ADR-0008's library) —
 * read from the parent's `form.state`, it would go on showing the figure from
 * two keystrokes ago.
 */
function WhatItWouldAsk({
  month,
  body,
  pending,
}: {
  month: string
  body: MetaCreate | null
  pending: boolean
}) {
  const preview = useQuery({
    queryKey: qk.metaPreview(body),
    queryFn: () => previewMeta(month, body as MetaCreate),
    enabled: body !== null,
  })
  const asks = preview.data?.asks ?? null
  const overTheMonth = preview.data?.over_the_month === true

  return (
    <>
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
      <Button type="submit" disabled={body === null || pending}>
        {overTheMonth ? "Crear de todos modos" : "Crear"}
      </Button>
    </>
  )
}

export function CreateMetaForm({ month, onDone }: { month: string; onDone: () => void }) {
  const queryClient = useQueryClient()
  const form = useTanStackForm({
    defaultValues: EMPTY,
    validators: { onChange: createMetaSchema },
    onSubmit: async ({ value }) => {
      const body = askable(value)
      if (body !== null) create.mutate(body)
    },
  })

  const create = useMutation({
    mutationFn: (body: MetaCreate) => createMeta(month, body),
    onSuccess: async () => {
      toast.success("Meta creada.")
      await invalidate(queryClient, "metaWrite")
      onDone()
    },
    onError: (error) => {
      applyApiErrorsToForm(form, error)
      toast.error(error instanceof ApiError ? error.message : "No se pudo crear la meta.")
    },
  })

  return (
    <form
      className="space-y-3 rounded-md border p-4"
      style={{ borderColor: "var(--border)" }}
      onSubmit={(event) => {
        event.preventDefault()
        event.stopPropagation()
        void form.handleSubmit()
      }}
    >
      <form.Field name="name">
        {(field) => (
          <div className="space-y-1.5">
            <Label htmlFor="meta-name">Nombre *</Label>
            <Input
              id="meta-name"
              value={field.state.value as string}
              onChange={(event) => field.handleChange(event.target.value as never)}
            />
          </div>
        )}
      </form.Field>

      <form.Field name="amount">
        {(field) => (
          <div className="space-y-1.5">
            <Label htmlFor="meta-amount">Cuánto * (COP)</Label>
            <MoneyInput
              id="meta-amount"
              currency="COP"
              value={Number.isFinite(field.state.value) ? (field.state.value as number) : null}
              onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
            />
          </div>
        )}
      </form.Field>

      <form.Field name="targetMonth">
        {(field) => (
          <div className="space-y-1.5">
            <Label htmlFor="meta-month">Cuándo *</Label>
            <Input
              id="meta-month"
              type="month"
              value={field.state.value as string}
              onChange={(event) => field.handleChange(event.target.value as never)}
            />
          </div>
        )}
      </form.Field>

      <form.Subscribe selector={(state) => askable(state.values)}>
        {(body) => (
          <div className="flex flex-wrap items-center gap-2">
            <WhatItWouldAsk month={month} body={body} pending={create.isPending} />
            <Button type="button" variant="ghost" onClick={onDone}>
              Cancelar
            </Button>
          </div>
        )}
      </form.Subscribe>
    </form>
  )
}
