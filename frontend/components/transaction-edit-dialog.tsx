"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useEffect } from "react"
import { toast } from "sonner"
import { EntitySelect } from "@/components/entity-select"
import { FormField } from "@/components/form-field"
import {
  type TransactionEditValues,
  txEditSchema,
} from "@/components/transaction-edit-dialog.schema"
import { listCategories } from "@/lib/api/categories"
import { updateTransaction } from "@/lib/api/transactions"
import { ApiError, applyApiErrorsToForm, type Transaction } from "@/lib/api/types"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Button, Dialog, DialogPopup, DialogTitle, Label } from "@/ui"

function emptyDefaults(): TransactionEditValues {
  return {
    payee: "",
    categoryId: null,
    date: "",
    notes: "",
  }
}

function valuesFromTx(tx: Transaction): TransactionEditValues {
  return {
    payee: tx.payee ?? "",
    categoryId: tx.category_id,
    date: tx.date,
    notes: tx.notes ?? "",
  }
}

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

  const form = useTanStackForm({
    defaultValues: emptyDefaults(),
    validators: { onChange: txEditSchema },
    onSubmit: async ({ value }) => {
      update.mutate(value)
    },
  })

  // Reseed form whenever a new tx is passed in.
  useEffect(() => {
    if (tx) {
      form.reset(valuesFromTx(tx))
    }
  }, [tx, form])

  const update = useMutation({
    mutationFn: (values: TransactionEditValues) => {
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
      form.reset(emptyDefaults())
      onOpenChange(false)
    },
    onError: (e: unknown) => {
      applyApiErrorsToForm(form, e)
      toast.error(e instanceof ApiError ? e.message : "Error")
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Editar transacción</DialogTitle>
        {tx && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              e.stopPropagation()
              void form.handleSubmit()
            }}
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
            <form.Field name="payee">
              {(field) => <FormField field={field} label="Beneficiario" />}
            </form.Field>
            <form.Field name="date">
              {(field) => <FormField field={field} label="Fecha" type="date" />}
            </form.Field>
            <form.Field name="categoryId">
              {(field) => (
                <div className="space-y-1.5">
                  <Label>Categoría</Label>
                  <EntitySelect
                    value={field.state.value as number | null}
                    onChange={(v) => field.handleChange(v as never)}
                    queryKey={qk.categories(false)}
                    queryFn={() => listCategories(false)}
                    allowNullLabel="Sin categoría"
                  />
                </div>
              )}
            </form.Field>
            <form.Field name="notes">
              {(field) => <FormField field={field} label="Notas" />}
            </form.Field>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={update.isPending || form.state.isSubmitting}>
                {update.isPending || form.state.isSubmitting ? "…" : "Guardar"}
              </Button>
            </div>
          </form>
        )}
      </DialogPopup>
    </Dialog>
  )
}
