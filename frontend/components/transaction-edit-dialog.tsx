"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { Controller, useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"
import { EntitySelect } from "@/components/entity-select"
import { FormField } from "@/components/form-field"
import { listCategories } from "@/lib/api/categories"
import { updateTransaction } from "@/lib/api/transactions"
import { ApiError, type Transaction } from "@/lib/api/types"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { isoDate, optionalString } from "@/lib/schemas/primitives"
import { Button, Dialog, DialogPopup, DialogTitle, Label } from "@/ui"

const txEditSchema = z.object({
  payee: optionalString,
  categoryId: z.number().nullable(),
  date: isoDate,
  notes: optionalString,
})
type TxEditValues = z.infer<typeof txEditSchema>

export function TransactionEditDialog({
  tx,
  open,
  onOpenChange,
}: {
  tx: Transaction | null
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const qc = useQueryClient()

  const form = useForm<TxEditValues>({
    resolver: zodResolver(txEditSchema),
    defaultValues: {
      payee: "",
      categoryId: null,
      date: "",
      notes: "",
    },
  })

  // Reseed form whenever a new tx is passed in.
  useEffect(() => {
    if (tx) {
      form.reset({
        payee: tx.payee ?? "",
        categoryId: tx.category_id,
        date: tx.date,
        notes: tx.notes ?? "",
      })
    }
  }, [tx, form])

  const update = useMutation({
    mutationFn: (values: TxEditValues) => {
      if (!tx) throw new Error("tx is required")
      return updateTransaction(tx.id, {
        payee: values.payee && values.payee.length > 0 ? values.payee : undefined,
        date: values.date,
        category_id: values.categoryId,
        notes: values.notes && values.notes.length > 0 ? values.notes : null,
      })
    },
    onSuccess: () => {
      toast.success("Transacción actualizada")
      invalidate(qc, "transactionWrite")
      onOpenChange(false)
    },
    onError: (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error"),
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Editar transacción</DialogTitle>
        {tx && (
          <form
            onSubmit={form.handleSubmit((values) => update.mutate(values))}
            className="space-y-4"
          >
            <div
              className="rounded-lg border p-3 text-sm"
              style={{ borderColor: "var(--border)", color: "var(--muted-foreground)" }}
            >
              <p>
                {tx.type} · {formatCents(tx.amount, tx.currency)} · cuenta #{tx.account_id}
              </p>
              <p className="mt-1 text-xs">Para cambiar monto/cuenta, elimina y vuelve a crear.</p>
            </div>
            <FormField control={form.control} name="payee" label="Beneficiario" />
            <FormField control={form.control} name="date" label="Fecha" type="date" />
            <Controller
              control={form.control}
              name="categoryId"
              render={({ field }) => (
                <div className="space-y-1.5">
                  <Label>Categoría</Label>
                  <EntitySelect
                    value={field.value}
                    onChange={field.onChange}
                    queryKey={qk.categories(false)}
                    queryFn={() => listCategories(false)}
                    allowNullLabel="Sin categoría"
                  />
                </div>
              )}
            />
            <FormField control={form.control} name="notes" label="Notas" />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={update.isPending}>
                {update.isPending ? "…" : "Guardar"}
              </Button>
            </div>
          </form>
        )}
      </DialogPopup>
    </Dialog>
  )
}
