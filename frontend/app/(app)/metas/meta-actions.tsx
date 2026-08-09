"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { type ReactNode, useState } from "react"
import { toast } from "sonner"
import { MoneyInput } from "@/components/money-input"
import { cancelMeta, closeMeta, contribute, setMeta } from "@/lib/api/metas"
import { ApiError, type MetaStatus } from "@/lib/api/types"
import { invalidate } from "@/lib/query"
import { Button, Input, Label } from "@/ui"
import { metaAmountSchema, metaMonthSchema } from "./metas.schema"

type Asking = "amount" | "month" | "contribution" | null

function useMetaWrite(done: () => void) {
  const queryClient = useQueryClient()
  return {
    settled: async (message: string) => {
      toast.success(message)
      await invalidate(queryClient, "metaWrite")
      done()
    },
    refused: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : "No se pudo hacer el cambio."),
  }
}

/**
 * One field, its label, and the two buttons that end it.
 *
 * The three things a meta can be asked for differ only in what goes between
 * them, so the chrome is written once.
 */
function InlineAsk({
  id,
  label,
  submitLabel,
  ready,
  pending,
  onSubmit,
  onCancel,
  children,
}: {
  id: string
  label: string
  submitLabel: string
  ready: boolean
  pending: boolean
  onSubmit: () => void
  onCancel: () => void
  children: ReactNode
}) {
  return (
    <form
      className="flex flex-wrap items-end gap-2 pt-1"
      onSubmit={(event) => {
        event.preventDefault()
        event.stopPropagation()
        onSubmit()
      }}
    >
      <div className="w-48 space-y-1">
        <Label htmlFor={id}>{label}</Label>
        {children}
      </div>
      <Button type="submit" size="sm" disabled={!ready || pending}>
        {submitLabel}
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
        Cancelar
      </Button>
    </form>
  )
}

/**
 * Money, asked for twice over with two meanings — a new target, or a
 * contribution. Two instances rather than one shared field, so the value the
 * owner typed for one can never arrive in the other.
 */
function AmountAsk({
  id,
  currency,
  label,
  submitLabel,
  pending,
  onDone,
  onSubmit,
}: {
  id: string
  currency: string
  label: string
  submitLabel: string
  pending: boolean
  onDone: () => void
  onSubmit: (cents: number) => void
}) {
  const form = useTanStackForm({
    defaultValues: { amount: Number.NaN },
    validators: { onChange: metaAmountSchema },
    onSubmit: async ({ value }) => onSubmit(value.amount),
  })
  return (
    <form.Subscribe selector={(state) => metaAmountSchema.safeParse(state.values).success}>
      {(ready) => (
        <InlineAsk
          id={id}
          label={label}
          submitLabel={submitLabel}
          ready={ready}
          pending={pending}
          onSubmit={() => void form.handleSubmit()}
          onCancel={onDone}
        >
          <form.Field name="amount">
            {(field) => (
              <MoneyInput
                id={id}
                currency={currency}
                value={Number.isFinite(field.state.value) ? field.state.value : null}
                onChange={(cents) => field.handleChange(cents ?? Number.NaN)}
              />
            )}
          </form.Field>
        </InlineAsk>
      )}
    </form.Subscribe>
  )
}

function MonthAsk({
  id,
  pending,
  onDone,
  onSubmit,
}: {
  id: string
  pending: boolean
  onDone: () => void
  onSubmit: (targetMonth: string) => void
}) {
  const form = useTanStackForm({
    defaultValues: { targetMonth: "" },
    validators: { onChange: metaMonthSchema },
    onSubmit: async ({ value }) => onSubmit(value.targetMonth),
  })
  return (
    <form.Subscribe selector={(state) => metaMonthSchema.safeParse(state.values).success}>
      {(ready) => (
        <InlineAsk
          id={id}
          label="Nuevo mes"
          submitLabel="Guardar"
          ready={ready}
          pending={pending}
          onSubmit={() => void form.handleSubmit()}
          onCancel={onDone}
        >
          <form.Field name="targetMonth">
            {(field) => (
              <Input
                id={id}
                type="month"
                value={field.state.value}
                onChange={(event) => field.handleChange(event.target.value)}
              />
            )}
          </form.Field>
        </InlineAsk>
      )}
    </form.Subscribe>
  )
}

/**
 * Everything the owner can do to a meta from the screen.
 *
 * Closing, raising the amount and moving the month are the three answers a
 * completed meta asks for (AC-8); putting money in by hand and cancelling are
 * open the whole time. Cancelling is not destructive — the meta is archived
 * and listed below, where it can be brought back (AC-29).
 */
export function MetaActions({ meta, month }: { meta: MetaStatus; month: string }) {
  const [asking, setAsking] = useState<Asking>(null)
  const write = useMetaWrite(() => setAsking(null))

  const close = useMutation({
    mutationFn: () => closeMeta(meta.meta_id, month),
    onSuccess: () => write.settled(`${meta.name} quedó cerrada.`),
    onError: write.refused,
  })
  const amend = useMutation({
    mutationFn: (body: { amount?: number; target_month?: string }) =>
      setMeta(meta.meta_id, month, body),
    onSuccess: () => write.settled(`${meta.name} sigue con lo nuevo.`),
    onError: write.refused,
  })
  const putIn = useMutation({
    mutationFn: (cents: number) => contribute(meta.meta_id, month, cents),
    onSuccess: () => write.settled(`Le pusiste plata a ${meta.name}.`),
    onError: write.refused,
  })
  const cancel = useMutation({
    mutationFn: () => cancelMeta(meta.meta_id, month),
    onSuccess: () => write.settled(`${meta.name} quedó cancelada. La puedes traer de vuelta.`),
    onError: write.refused,
  })

  const busy = close.isPending || amend.isPending || putIn.isPending || cancel.isPending
  const answering = meta.complete && !meta.closed
  const done = () => setAsking(null)

  if (asking === "amount") {
    return (
      <AmountAsk
        id={`meta-${meta.meta_id}-amount`}
        currency={meta.currency}
        label={`Nuevo monto (${meta.currency})`}
        submitLabel="Guardar"
        pending={busy}
        onDone={done}
        onSubmit={(amount) => amend.mutate({ amount })}
      />
    )
  }

  if (asking === "month") {
    return (
      <MonthAsk
        id={`meta-${meta.meta_id}-month`}
        pending={busy}
        onDone={done}
        onSubmit={(target_month) => amend.mutate({ target_month })}
      />
    )
  }

  if (asking === "contribution") {
    return (
      <AmountAsk
        id={`meta-${meta.meta_id}-put`}
        currency={meta.currency}
        label={`Cuánto le pones (${meta.currency})`}
        submitLabel="Ponerla"
        pending={busy}
        onDone={done}
        onSubmit={(amount) => putIn.mutate(amount)}
      />
    )
  }

  return (
    <div className="flex flex-wrap gap-2 pt-1">
      {answering ? (
        <>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => close.mutate()}>
            Cerrar {meta.name}
          </Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => setAsking("amount")}>
            Seguir con otro monto
          </Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => setAsking("month")}>
            Seguir con otro mes
          </Button>
        </>
      ) : (
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => setAsking("contribution")}>
          Ponerle plata
        </Button>
      )}
      <Button variant="ghost" size="sm" disabled={busy} onClick={() => cancel.mutate()}>
        Cancelar {meta.name}
      </Button>
    </div>
  )
}
