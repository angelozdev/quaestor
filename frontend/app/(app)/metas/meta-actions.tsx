"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { type ReactNode, useState } from "react"
import { toast } from "sonner"
import { MoneyInput } from "@/components/money-input"
import {
  cancelMeta,
  closeMeta,
  contribute,
  listContributions,
  removeContribution,
  setMeta,
} from "@/lib/api/metas"
import { ApiError, type MetaStatus } from "@/lib/api/types"
import { monthNameOf } from "@/lib/date"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Button, Input, Label } from "@/ui"
import { type AskedText, metaAmountSchema, metaMonthSchema, metaNameSchema } from "./metas.schema"

type Asking = "name" | "amount" | "month" | "contribution" | "contributions" | null

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

/**
 * One line of text a running meta is asked for — its new name, or its new month.
 *
 * The rule that judges what was typed is the only thing that changes between
 * them, so it arrives as an argument rather than as a second component.
 */
function TextAsk({
  id,
  label,
  type,
  initial,
  schema,
  pending,
  onDone,
  onSubmit,
}: {
  id: string
  label: string
  type?: "month"
  initial: string
  schema: AskedText
  pending: boolean
  onDone: () => void
  onSubmit: (value: string) => void
}) {
  const form = useTanStackForm({
    defaultValues: { value: initial },
    validators: { onChange: schema },
    onSubmit: async ({ value }) => onSubmit(value.value),
  })
  return (
    <form.Subscribe selector={(state) => schema.safeParse(state.values).success}>
      {(ready) => (
        <InlineAsk
          id={id}
          label={label}
          submitLabel="Guardar"
          ready={ready}
          pending={pending}
          onSubmit={() => void form.handleSubmit()}
          onCancel={onDone}
        >
          <form.Field name="value">
            {(field) => (
              <Input
                id={id}
                type={type}
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
 * Every contribution the owner made to one meta, and the way to undo one (AC-42).
 *
 * Removing one is not destructive to the meta: the month it was made in gets
 * its money back and the instalments that follow rise again, which is the
 * remedy a contribution typed into the wrong meta had none of.
 *
 * One a cancellation gave back (ADR-0055) is struck through and says so: it is
 * still the owner's history, and it is no longer part of what the meta holds.
 */
function ContributionsList({ meta, onDone }: { meta: MetaStatus; onDone: () => void }) {
  const queryClient = useQueryClient()
  const list = useQuery({
    queryKey: qk.metaContributions(meta.meta_id),
    queryFn: () => listContributions(meta.meta_id),
  })
  const remove = useMutation({
    mutationFn: (id: number) => removeContribution(id),
    onSuccess: async () => {
      toast.success(`El aporte volvió a su mes.`)
      await invalidate(queryClient, "metaWrite")
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : "No se pudo quitar el aporte."),
  })

  return (
    <div className="space-y-2 pt-1">
      {list.data && list.data.length === 0 && (
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          No le has puesto plata a mano.
        </p>
      )}
      {list.data && list.data.length > 0 && (
        <ul className="space-y-1">
          {list.data.map((contribution) => {
            const givenBack = contribution.returned_month !== null
            return (
              <li key={contribution.id} className="flex flex-wrap items-center gap-3 text-sm">
                <span style={{ color: "var(--muted-foreground)" }}>
                  {monthNameOf(contribution.year_month)} {contribution.year_month.slice(0, 4)}
                </span>
                <span
                  className={givenBack ? "tabular-nums line-through" : "tabular-nums"}
                  style={givenBack ? { color: "var(--muted-foreground)" } : undefined}
                >
                  {formatCents(contribution.amount, meta.currency)}
                </span>
                {givenBack && (
                  <span className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                    Te lo devolvimos al cancelar la meta.
                  </span>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={remove.isPending}
                  onClick={() => remove.mutate(contribution.id)}
                >
                  Quitar
                </Button>
              </li>
            )
          })}
        </ul>
      )}
      <Button variant="ghost" size="sm" onClick={onDone}>
        Listo
      </Button>
    </div>
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
    mutationFn: (body: { name?: string; amount?: number; target_month?: string }) =>
      setMeta(meta.meta_id, month, body),
    onSuccess: () => write.settled(`${meta.name} sigue con lo nuevo.`),
    onError: write.refused,
  })
  const putIn = useMutation({
    mutationFn: (cents: number) => contribute(meta.meta_id, month, cents),
    onSuccess: (made) =>
      write.settled(`Le pusiste ${formatCents(made.amount, meta.currency)} a ${meta.name}.`),
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

  if (asking === "name") {
    return (
      <TextAsk
        id={`meta-${meta.meta_id}-name`}
        label="Nuevo nombre"
        initial={meta.name}
        schema={metaNameSchema}
        pending={busy}
        onDone={done}
        onSubmit={(name) => amend.mutate({ name })}
      />
    )
  }

  if (asking === "contributions") {
    return <ContributionsList meta={meta} onDone={done} />
  }

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
      <TextAsk
        id={`meta-${meta.meta_id}-month`}
        label="Nuevo mes"
        type="month"
        initial=""
        schema={metaMonthSchema}
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
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => close.mutate()}>
          Cerrar {meta.name}
        </Button>
      ) : (
        <Button variant="ghost" size="sm" disabled={busy} onClick={() => setAsking("contribution")}>
          Ponerle plata
        </Button>
      )}
      <Button variant="ghost" size="sm" disabled={busy} onClick={() => setAsking("name")}>
        Cambiarle el nombre
      </Button>
      <Button variant="ghost" size="sm" disabled={busy} onClick={() => setAsking("amount")}>
        {answering ? "Seguir con otro monto" : "Cambiarle el monto"}
      </Button>
      <Button variant="ghost" size="sm" disabled={busy} onClick={() => setAsking("month")}>
        {answering ? "Seguir con otro mes" : "Cambiarle el mes"}
      </Button>
      <Button variant="ghost" size="sm" disabled={busy} onClick={() => setAsking("contributions")}>
        Ver aportes
      </Button>
      <Button variant="ghost" size="sm" disabled={busy} onClick={() => cancel.mutate()}>
        Cancelar {meta.name}
      </Button>
    </div>
  )
}
