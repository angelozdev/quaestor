"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { EntitySelect } from "@/components/entity-select"
import { FormField } from "@/components/form-field"
import { TagChipsInput } from "@/components/tag-chips-input"
import {
  type TransactionEditValues,
  txEditSchema,
} from "@/components/transaction-edit-dialog.schema"
import { listAccounts } from "@/lib/api/accounts"
import { listCategories } from "@/lib/api/categories"
import { listTransactions, updateTransaction } from "@/lib/api/transactions"
import { ApiError, applyApiErrorsToForm, type Transaction } from "@/lib/api/types"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { findCounterpart } from "@/lib/transfers"
import { useTagNames } from "@/lib/use-tag-names"
import { Badge, Button, Dialog, DialogPopup, DialogTitle, Label } from "@/ui"

function valuesFromTx(tx: Transaction): TransactionEditValues {
  return {
    payee: tx.payee ?? "",
    categoryId: tx.category_id,
    date: tx.date,
    notes: tx.notes ?? "",
    tags: tx.tags,
  }
}

function TransferPairInfo({ tx }: { tx: Transaction }) {
  const groupFilter = { transfer_group_id: tx.transfer_group_id ?? undefined }
  const siblings = useQuery({
    queryKey: qk.transactions(groupFilter),
    queryFn: () => listTransactions(groupFilter),
  })
  const accounts = useQuery({
    queryKey: qk.accounts(true),
    queryFn: () => listAccounts(true),
  })
  const counterpart = findCounterpart(siblings.data, tx)
  const accountName = (id: number) =>
    accounts.data?.find((a) => a.id === id)?.name ?? `cuenta #${id}`

  return (
    <div className="space-y-1">
      <Badge variant="secondary">Parte de una transferencia</Badge>
      {counterpart && (
        <p className="text-xs">
          {tx.transfer_direction === "out"
            ? "Enviada a"
            : tx.transfer_direction === "in"
              ? "Recibida de"
              : "Contraparte:"}{" "}
          {accountName(counterpart.account_id)} ·{" "}
          {formatCents(counterpart.amount, counterpart.currency)}
        </p>
      )}
    </div>
  )
}

function EditTransactionForm({ tx, onDone }: { tx: Transaction; onDone: () => void }) {
  const qc = useQueryClient()
  const tagSuggestions = useTagNames()
  const isTransfer = tx.type === "transfer"
  const isIncome = tx.type === "income"

  const form = useTanStackForm({
    defaultValues: valuesFromTx(tx),
    validators: { onChange: txEditSchema(isTransfer) },
    onSubmit: async ({ value }) => {
      update.mutate(value)
    },
  })

  const update = useMutation({
    mutationFn: (values: TransactionEditValues) =>
      updateTransaction(tx.id, {
        payee: values.payee && values.payee.length > 0 ? values.payee : undefined,
        date: values.date,
        category_id: values.categoryId,
        notes: values.notes && values.notes.length > 0 ? values.notes : null,
        tags: values.tags,
      }),
    onSuccess: () => {
      toast.success("Transacción actualizada")
      invalidate(qc, "transactionWrite")
      onDone()
    },
    onError: (e: unknown) => {
      applyApiErrorsToForm(form, e)
      toast.error(e instanceof ApiError ? e.message : "Error")
    },
  })

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        e.stopPropagation()
        void form.handleSubmit()
      }}
      className="space-y-4"
    >
      <div
        className="space-y-2 rounded-lg border p-3 text-sm"
        style={{ borderColor: "var(--border)", color: "var(--muted-foreground)" }}
      >
        {tx.transfer_group_id && <TransferPairInfo tx={tx} />}
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
      {!isTransfer && (
        <form.Field name="categoryId">
          {(field) => (
            <div className="space-y-1.5">
              <Label htmlFor="tx-edit-category">Categoría *</Label>
              <EntitySelect
                id="tx-edit-category"
                value={field.state.value as number | null}
                onChange={(v) => field.handleChange(v as never)}
                queryKey={qk.categories(false, isIncome)}
                queryFn={() => listCategories(false, isIncome)}
              />
              {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                <p className="text-xs text-destructive">
                  {(field.state.meta.errors[0] as { message?: string }).message}
                </p>
              )}
            </div>
          )}
        </form.Field>
      )}
      <form.Field name="tags">
        {(field) => (
          <TagChipsInput
            value={field.state.value as string[]}
            onChange={(tags) => field.handleChange(tags as never)}
            suggestions={tagSuggestions}
          />
        )}
      </form.Field>
      <form.Field name="notes">{(field) => <FormField field={field} label="Notas" />}</form.Field>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onDone}>
          Cancelar
        </Button>
        <Button type="submit" disabled={update.isPending || form.state.isSubmitting}>
          {update.isPending || form.state.isSubmitting ? "…" : "Guardar"}
        </Button>
      </div>
    </form>
  )
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
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>Editar transacción</DialogTitle>
        {tx && <EditTransactionForm key={tx.id} tx={tx} onDone={() => onOpenChange(false)} />}
      </DialogPopup>
    </Dialog>
  )
}
