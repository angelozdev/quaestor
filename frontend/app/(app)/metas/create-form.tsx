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
import { Button, Input, Label, Select } from "@/ui"
import { type CreateMetaValues, createMetaSchema, META_CURRENCIES } from "./metas.schema"

const EMPTY: CreateMetaValues = {
  name: "",
  amount: Number.NaN,
  targetMonth: "",
  currency: "COP",
  statedOpening: undefined,
}

const CURRENCY_ITEMS = META_CURRENCIES.map((code) => ({ value: code, label: code }))

/** An amount the form asks for, with the label and the note that explain it. */
function MoneyField({
  id,
  label,
  currency,
  value,
  onChange,
  hint,
}: {
  id: string
  label: string
  currency: string
  value: number | null
  onChange: (cents: number | null) => void
  hint?: string
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <MoneyInput id={id} currency={currency} value={value} onChange={onChange} />
      {hint !== undefined && (
        <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
          {hint}
        </p>
      )}
    </div>
  )
}

/** What the form knows before it is complete enough to ask the server anything. */
function askable(values: CreateMetaValues): MetaCreate | null {
  const parsed = createMetaSchema.safeParse(values)
  return parsed.success
    ? {
        name: parsed.data.name,
        amount: parsed.data.amount,
        target_month: parsed.data.targetMonth,
        currency: parsed.data.currency,
        stated_opening: parsed.data.statedOpening ?? null,
      }
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
  const refused = preview.isError

  return (
    <>
      {asks !== null && (
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          Te pediría {formatCents(asks, body?.currency ?? "COP")} al mes.
        </p>
      )}
      {refused && (
        <p role="alert" className="text-sm" style={{ color: "var(--destructive)" }}>
          Con esos números no se puede crear la meta.
        </p>
      )}
      {overTheMonth && (
        <p role="alert" className="text-sm" style={{ color: "var(--destructive)" }}>
          Es más de lo que tu mes tiene.
        </p>
      )}
      <Button type="submit" disabled={body === null || pending || refused}>
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

      <form.Field name="currency">
        {(currencyField) => (
          <>
            <div className="space-y-1.5">
              <Label htmlFor="meta-currency">En qué moneda *</Label>
              <Select
                id="meta-currency"
                items={CURRENCY_ITEMS}
                value={currencyField.state.value as string}
                onValueChange={(code) => currencyField.handleChange((code ?? "COP") as never)}
              />
            </div>

            <form.Field name="amount">
              {(field) => (
                <MoneyField
                  id="meta-amount"
                  label={`Cuánto * (${currencyField.state.value as string})`}
                  currency={currencyField.state.value as string}
                  value={Number.isFinite(field.state.value) ? (field.state.value as number) : null}
                  onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                />
              )}
            </form.Field>

            <form.Field name="statedOpening">
              {(field) => (
                <MoneyField
                  id="meta-opening"
                  label="Ya tenía guardado"
                  currency={currencyField.state.value as string}
                  value={Number.isFinite(field.state.value) ? (field.state.value as number) : null}
                  onChange={(cents) => field.handleChange((cents ?? undefined) as never)}
                  hint="Plata que ya habías apartado antes de crear la meta. No le cuesta nada a este mes."
                />
              )}
            </form.Field>
          </>
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
