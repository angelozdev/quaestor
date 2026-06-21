"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { EntitySelect } from "@/components/entity-select"
import { FormField } from "@/components/form-field"
import { MoneyInput } from "@/components/money-input"
import {
  type TxNormalValues,
  type TxTransferValues,
  txNormalSchema,
  txTransferSchema,
} from "@/components/transaction-create-dialog.schema"
import { listAccounts } from "@/lib/api/accounts"
import { listCategories } from "@/lib/api/categories"
import { createTransaction, createTransfer as createTransferApi } from "@/lib/api/transactions"
import { type Account, ApiError, applyApiErrorsToForm } from "@/lib/api/types"
import { invalidate, qk } from "@/lib/query"
import {
  Button,
  Dialog,
  DialogPopup,
  DialogTitle,
  Label,
  Select,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/ui"

const TYPE_ITEMS = [
  { value: "expense", label: "Gasto" },
  { value: "income", label: "Ingreso" },
]

const NORMAL_DEFAULTS: TxNormalValues = {
  type: "expense",
  accountId: null,
  amount: Number.NaN,
  categoryId: null,
  date: new Date().toISOString().slice(0, 10),
  payee: "",
  fxRate: Number.NaN,
  notes: "",
}

const TRANSFER_DEFAULTS: TxTransferValues = {
  fromId: null,
  toId: null,
  amount: Number.NaN,
  date: new Date().toISOString().slice(0, 10),
  fxRate: Number.NaN,
  notes: "",
}

function currencyOf(accounts: Account[] | undefined, id: number | null): string {
  if (id === null) return "COP"
  return accounts?.find((a) => a.id === id)?.currency ?? "COP"
}

export function TransactionCreateDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
}) {
  const qc = useQueryClient()
  const accounts = useQuery({
    queryKey: qk.accounts(false),
    queryFn: () => listAccounts(false),
  })

  const normalForm = useTanStackForm({
    defaultValues: NORMAL_DEFAULTS,
    validators: { onChange: txNormalSchema },
    onSubmit: async ({ value }) => {
      createNormal.mutate(value)
    },
  })

  const transferForm = useTanStackForm({
    defaultValues: TRANSFER_DEFAULTS,
    validators: { onChange: txTransferSchema },
    onSubmit: async ({ value }) => {
      createTransfer.mutate(value)
    },
  })

  const normalCurrency = currencyOf(accounts.data, normalForm.getFieldValue("accountId"))
  const transferCurrency = currencyOf(accounts.data, transferForm.getFieldValue("fromId"))

  function resetForms() {
    normalForm.reset(NORMAL_DEFAULTS)
    transferForm.reset(TRANSFER_DEFAULTS)
  }

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")

  const done = (msg: string) => {
    toast.success(msg)
    invalidate(qc, "transactionWrite")
    onOpenChange(false)
    resetForms()
  }

  const createNormal = useMutation({
    mutationFn: (values: TxNormalValues) => {
      return createTransaction({
        type: values.type,
        account_id: values.accountId as number,
        amount: values.amount,
        currency: normalCurrency,
        date: values.date,
        payee: values.payee && values.payee.length > 0 ? values.payee : undefined,
        category_id: values.categoryId,
        notes: values.notes && values.notes.length > 0 ? values.notes : undefined,
        fx_rate:
          normalCurrency !== "COP" && Number.isFinite(values.fxRate)
            ? String(values.fxRate)
            : undefined,
      })
    },
    onSuccess: () => done("Transacción creada"),
    onError: (e: unknown) => {
      applyApiErrorsToForm(normalForm, e)
      onErr(e)
    },
  })

  const createTransfer = useMutation({
    mutationFn: (values: TxTransferValues) => {
      return createTransferApi({
        from_account_id: values.fromId as number,
        to_account_id: values.toId as number,
        amount: values.amount,
        currency: transferCurrency,
        date: values.date,
        notes: values.notes && values.notes.length > 0 ? values.notes : undefined,
        fx_rate:
          transferCurrency !== "COP" && Number.isFinite(values.fxRate)
            ? String(values.fxRate)
            : undefined,
      })
    },
    onSuccess: () => done("Transferencia creada"),
    onError: (e: unknown) => {
      applyApiErrorsToForm(transferForm, e)
      onErr(e)
    },
  })

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) resetForms()
        onOpenChange(o)
      }}
    >
      <DialogPopup className="max-w-lg">
        <DialogTitle>Nueva transacción</DialogTitle>
        <Tabs defaultValue="normal">
          <TabsList>
            <TabsTrigger value="normal">Normal</TabsTrigger>
            <TabsTrigger value="transfer">Transferencia</TabsTrigger>
          </TabsList>

          <TabsContent value="normal">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                e.stopPropagation()
                void normalForm.handleSubmit()
              }}
              className="space-y-4 pt-2"
            >
              <normalForm.Field name="type">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Tipo *</Label>
                    <Select
                      value={field.state.value as string}
                      onValueChange={(v) => v && field.handleChange(v as never)}
                      items={TYPE_ITEMS}
                    />
                  </div>
                )}
              </normalForm.Field>
              <normalForm.Field name="accountId">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Cuenta *</Label>
                    <EntitySelect
                      value={field.state.value as number | null}
                      onChange={(v) => field.handleChange(v as never)}
                      queryKey={qk.accounts(false)}
                      queryFn={() => listAccounts(false)}
                    />
                    {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                      <p className="text-xs text-destructive">
                        {String((field.state.meta.errors[0] as { message?: string })?.message)}
                      </p>
                    )}
                  </div>
                )}
              </normalForm.Field>
              <normalForm.Field name="amount">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Monto * ({normalCurrency})</Label>
                    <MoneyInput
                      currency={normalCurrency}
                      value={
                        typeof field.state.value === "number" && Number.isFinite(field.state.value)
                          ? (field.state.value as number)
                          : null
                      }
                      onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                    />
                    {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                      <p className="text-xs text-destructive">
                        {String((field.state.meta.errors[0] as { message?: string })?.message)}
                      </p>
                    )}
                  </div>
                )}
              </normalForm.Field>
              <normalForm.Field name="date">
                {(field) => <FormField field={field} label="Fecha" type="date" />}
              </normalForm.Field>
              <normalForm.Field name="payee">
                {(field) => <FormField field={field} label="Beneficiario" />}
              </normalForm.Field>
              <normalForm.Field name="categoryId">
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
              </normalForm.Field>
              {normalCurrency !== "COP" && (
                <normalForm.Field name="fxRate">
                  {(field) => (
                    <FormField
                      field={field}
                      label="Tasa USD→COP (opcional)"
                      type="number"
                      placeholder="Se resuelve sola si la dejas vacía"
                      valueAsNumber
                    />
                  )}
                </normalForm.Field>
              )}
              <normalForm.Field name="notes">
                {(field) => <FormField field={field} label="Notas" />}
              </normalForm.Field>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                  Cancelar
                </Button>
                <Button
                  type="submit"
                  disabled={createNormal.isPending || normalForm.state.isSubmitting}
                >
                  {createNormal.isPending || normalForm.state.isSubmitting ? "…" : "Crear"}
                </Button>
              </div>
            </form>
          </TabsContent>

          <TabsContent value="transfer">
            <form
              onSubmit={(e) => {
                e.preventDefault()
                e.stopPropagation()
                void transferForm.handleSubmit()
              }}
              className="space-y-4 pt-2"
            >
              <transferForm.Field name="fromId">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Desde *</Label>
                    <EntitySelect
                      value={field.state.value as number | null}
                      onChange={(v) => field.handleChange(v as never)}
                      queryKey={qk.accounts(false)}
                      queryFn={() => listAccounts(false)}
                    />
                    {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                      <p className="text-xs text-destructive">
                        {String((field.state.meta.errors[0] as { message?: string })?.message)}
                      </p>
                    )}
                  </div>
                )}
              </transferForm.Field>
              <transferForm.Field name="toId">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Hacia *</Label>
                    <EntitySelect
                      value={field.state.value as number | null}
                      onChange={(v) => field.handleChange(v as never)}
                      queryKey={qk.accounts(false)}
                      queryFn={() => listAccounts(false)}
                    />
                    {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                      <p className="text-xs text-destructive">
                        {String((field.state.meta.errors[0] as { message?: string })?.message)}
                      </p>
                    )}
                  </div>
                )}
              </transferForm.Field>
              <transferForm.Field name="amount">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Monto * ({transferCurrency})</Label>
                    <MoneyInput
                      currency={transferCurrency}
                      value={
                        typeof field.state.value === "number" && Number.isFinite(field.state.value)
                          ? (field.state.value as number)
                          : null
                      }
                      onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                    />
                    {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                      <p className="text-xs text-destructive">
                        {String((field.state.meta.errors[0] as { message?: string })?.message)}
                      </p>
                    )}
                  </div>
                )}
              </transferForm.Field>
              <transferForm.Field name="date">
                {(field) => <FormField field={field} label="Fecha" type="date" />}
              </transferForm.Field>
              {transferCurrency !== "COP" && (
                <transferForm.Field name="fxRate">
                  {(field) => (
                    <FormField
                      field={field}
                      label="Tasa USD→COP (opcional)"
                      type="number"
                      valueAsNumber
                    />
                  )}
                </transferForm.Field>
              )}
              <transferForm.Field name="notes">
                {(field) => <FormField field={field} label="Notas" />}
              </transferForm.Field>
              <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                Ambas cuentas deben tener la misma moneda.
              </p>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                  Cancelar
                </Button>
                <Button
                  type="submit"
                  disabled={createTransfer.isPending || transferForm.state.isSubmitting}
                >
                  {createTransfer.isPending || transferForm.state.isSubmitting ? "…" : "Crear"}
                </Button>
              </div>
            </form>
          </TabsContent>
        </Tabs>
      </DialogPopup>
    </Dialog>
  )
}
