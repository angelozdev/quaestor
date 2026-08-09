"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { MoneyInput } from "@/components/money-input"
import { cancelMeta, closeMeta, contribute, setMeta } from "@/lib/api/metas"
import { ApiError, type MetaStatus } from "@/lib/api/types"
import { invalidate } from "@/lib/query"
import { Button, Input, Label } from "@/ui"

type Editing = "amount" | "month" | "contribution" | null

function useMetaWrite(done: () => void) {
  const queryClient = useQueryClient()
  return {
    onSuccess: async (message: string) => {
      toast.success(message)
      await invalidate(queryClient, "metaWrite")
      done()
    },
    onError: (error: unknown) =>
      toast.error(error instanceof ApiError ? error.message : "No se pudo hacer el cambio."),
  }
}

/**
 * Everything the owner can do to a meta from the screen.
 *
 * Closing, raising the amount and moving the month are the three answers a
 * completed meta asks for (AC-8); putting money in by hand and cancelling are
 * open the whole time. Cancelling is not destructive — the meta is archived
 * and listed below, where it can be brought back (AC-29) — so it asks nothing
 * before doing it, and says where the meta went.
 */
export function MetaActions({ meta, month }: { meta: MetaStatus; month: string }) {
  const [editing, setEditing] = useState<Editing>(null)
  const [amount, setAmount] = useState<number | null>(null)
  const [targetMonth, setTargetMonth] = useState("")
  const hooks = useMetaWrite(() => {
    setEditing(null)
    setAmount(null)
    setTargetMonth("")
  })

  const close = useMutation({
    mutationFn: () => closeMeta(meta.meta_id),
    onSuccess: () => hooks.onSuccess(`${meta.name} quedó cerrada.`),
    onError: hooks.onError,
  })
  const amend = useMutation({
    mutationFn: (body: { amount?: number; target_month?: string }) =>
      setMeta(meta.meta_id, month, body),
    onSuccess: () => hooks.onSuccess(`${meta.name} sigue con lo nuevo.`),
    onError: hooks.onError,
  })
  const putIn = useMutation({
    mutationFn: (cents: number) => contribute(meta.meta_id, month, cents),
    onSuccess: () => hooks.onSuccess(`Le pusiste plata a ${meta.name}.`),
    onError: hooks.onError,
  })
  const cancel = useMutation({
    mutationFn: () => cancelMeta(meta.meta_id, month),
    onSuccess: () => hooks.onSuccess(`${meta.name} quedó cancelada. La puedes traer de vuelta.`),
    onError: hooks.onError,
  })

  const busy = close.isPending || amend.isPending || putIn.isPending || cancel.isPending
  const answering = meta.complete && !meta.closed

  if (editing === "amount") {
    return (
      <form
        className="flex flex-wrap items-end gap-2 pt-1"
        onSubmit={(event) => {
          event.preventDefault()
          if (amount !== null) amend.mutate({ amount })
        }}
      >
        <div className="w-48 space-y-1">
          <Label htmlFor={`meta-${meta.meta_id}-amount`}>Nuevo monto ({meta.currency})</Label>
          <MoneyInput
            id={`meta-${meta.meta_id}-amount`}
            currency={meta.currency}
            value={amount}
            onChange={setAmount}
          />
        </div>
        <Button type="submit" size="sm" disabled={amount === null || busy}>
          Guardar
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(null)}>
          Cancelar
        </Button>
      </form>
    )
  }

  if (editing === "month") {
    return (
      <form
        className="flex flex-wrap items-end gap-2 pt-1"
        onSubmit={(event) => {
          event.preventDefault()
          if (/^\d{4}-\d{2}$/.test(targetMonth)) amend.mutate({ target_month: targetMonth })
        }}
      >
        <div className="w-48 space-y-1">
          <Label htmlFor={`meta-${meta.meta_id}-month`}>Nuevo mes</Label>
          <Input
            id={`meta-${meta.meta_id}-month`}
            type="month"
            value={targetMonth}
            onChange={(event) => setTargetMonth(event.target.value)}
          />
        </div>
        <Button type="submit" size="sm" disabled={targetMonth === "" || busy}>
          Guardar
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(null)}>
          Cancelar
        </Button>
      </form>
    )
  }

  if (editing === "contribution") {
    return (
      <form
        className="flex flex-wrap items-end gap-2 pt-1"
        onSubmit={(event) => {
          event.preventDefault()
          if (amount !== null) putIn.mutate(amount)
        }}
      >
        <div className="w-48 space-y-1">
          <Label htmlFor={`meta-${meta.meta_id}-put`}>Cuánto le pones ({meta.currency})</Label>
          <MoneyInput
            id={`meta-${meta.meta_id}-put`}
            currency={meta.currency}
            value={amount}
            onChange={setAmount}
          />
        </div>
        <Button type="submit" size="sm" disabled={amount === null || busy}>
          Ponerla
        </Button>
        <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(null)}>
          Cancelar
        </Button>
      </form>
    )
  }

  return (
    <div className="flex flex-wrap gap-2 pt-1">
      {answering && (
        <>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => close.mutate()}>
            Cerrar {meta.name}
          </Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => setEditing("amount")}>
            Seguir con otro monto
          </Button>
          <Button variant="ghost" size="sm" disabled={busy} onClick={() => setEditing("month")}>
            Seguir con otro mes
          </Button>
        </>
      )}
      {!answering && (
        <Button
          variant="ghost"
          size="sm"
          disabled={busy}
          onClick={() => setEditing("contribution")}
        >
          Ponerle plata
        </Button>
      )}
      <Button variant="ghost" size="sm" disabled={busy} onClick={() => cancel.mutate()}>
        Cancelar {meta.name}
      </Button>
    </div>
  )
}
