"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { QueryBoundary } from "@/components/query-boundary"
import { acceptPendingDates, declinePendingDates, pendingDates } from "@/lib/api/recurring"
import { ApiError } from "@/lib/api/types"
import { formatDate } from "@/lib/date"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import {
  Button,
  Checkbox,
  Dialog,
  DialogDescription,
  DialogPopup,
  DialogTitle,
  Skeleton,
} from "@/ui"

export interface PendingDatesSubject {
  id: number
  name: string
  amount: number
  currency: string
}

export function PendingDatesDialog({
  recurring,
  onOpenChange,
}: {
  recurring: PendingDatesSubject
  onOpenChange: (open: boolean) => void
}) {
  const [ticked, setTicked] = useState<string[]>([])
  const qc = useQueryClient()

  const dates = useQuery({
    queryKey: qk.pendingDates(recurring.id),
    queryFn: () => pendingDates(recurring.id),
  })

  const settle = (message: string) => {
    toast.success(message)
    invalidate(qc, "recurringWrite")
    setTicked([])
    onOpenChange(false)
  }

  const onErr = (e: unknown) =>
    toast.error(e instanceof ApiError ? e.message : "No se pudo guardar")

  const accept = useMutation({
    mutationFn: () => acceptPendingDates(recurring.id, ticked),
    onSuccess: () => settle(`Se registraron ${ticked.length} fecha(s)`),
    onError: onErr,
  })

  const decline = useMutation({
    mutationFn: () => declinePendingDates(recurring.id, dates.data ?? []),
    onSuccess: () => settle("Se descartaron las fechas pendientes"),
    onError: onErr,
  })

  const toggle = (date: string) =>
    setTicked((current) =>
      current.includes(date) ? current.filter((d) => d !== date) : [...current, date],
    )

  const pending = accept.isPending || decline.isPending

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogPopup className="max-w-md">
        <DialogTitle>Fechas pendientes de {recurring.name}</DialogTitle>
        <DialogDescription>
          Estas fechas ya vencieron cuando declaraste la obligación. Marca las que sí debes
          registrar; nada se cobra hasta que respondas.
        </DialogDescription>

        <QueryBoundary
          query={dates}
          skeleton={<Skeleton className="h-24 w-full" />}
          empty={{
            when: (d) => d.length === 0,
            node: (
              <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                No hay fechas pendientes.
              </p>
            ),
          }}
          errorMessage="No se pudieron cargar las fechas pendientes"
        >
          {(offered) => (
            <ul className="flex flex-col gap-2">
              {offered.map((date) => (
                <li key={date} className="flex items-center gap-3">
                  <Checkbox
                    id={`pending-${date}`}
                    checked={ticked.includes(date)}
                    onCheckedChange={() => toggle(date)}
                    disabled={pending}
                  />
                  <label htmlFor={`pending-${date}`} className="flex-1 text-sm">
                    {formatDate(date)}
                  </label>
                  <span className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                    {formatCents(recurring.amount, recurring.currency)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </QueryBoundary>

        <div className="flex justify-end gap-2">
          <Button
            variant="ghost"
            onClick={() => decline.mutate()}
            disabled={pending || !dates.data?.length}
          >
            Descartar todas
          </Button>
          <Button onClick={() => accept.mutate()} disabled={pending || ticked.length === 0}>
            Registrar {ticked.length || ""}
          </Button>
        </div>
      </DialogPopup>
    </Dialog>
  )
}
