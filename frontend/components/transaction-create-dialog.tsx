"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"
import { CategoryField } from "@/components/category-field"
import { EntitySelect } from "@/components/entity-select"
import { FormField } from "@/components/form-field"
import { MetaField } from "@/components/meta-field"
import { MoneyInput } from "@/components/money-input"
import { SettlesChargeField } from "@/components/settles-charge-field"
import { TagChipsInput } from "@/components/tag-chips-input"
import {
  type TxNormalValues,
  type TxTransferValues,
  txNormalSchema,
  txTransferSchema,
} from "@/components/transaction-create-dialog.schema"
import { TransferReceivedField } from "@/components/transfer-received-field"
import { listAccounts } from "@/lib/api/accounts"
import { createTransaction, createTransfer as createTransferApi } from "@/lib/api/transactions"
import { ApiError, applyApiErrorsToForm } from "@/lib/api/types"
import { yearMonthOf } from "@/lib/date"
import { currencyOf, finiteOrNull } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { useFormValues } from "@/lib/use-form-values"
import { useTagNames } from "@/lib/use-tag-names"
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
  newCategory: "",
  date: new Date().toISOString().slice(0, 10),
  payee: "",
  notes: "",
  tags: [],
  metaId: null,
  settlesCharge: null,
}

const TRANSFER_DEFAULTS: TxTransferValues = {
  fromId: null,
  toId: null,
  amount: Number.NaN,
  amountReceived: Number.NaN,
  date: new Date().toISOString().slice(0, 10),
  notes: "",
}

type FieldWithErrors = { state: { meta: { errors: unknown[] } } }

function fieldError(field: FieldWithErrors): string | undefined {
  const error = field.state.meta.errors[0] as { message?: string } | undefined
  return error?.message
}

function FieldError({ field }: { field: FieldWithErrors }) {
  const message = fieldError(field)
  if (!message) return null
  return <p className="text-xs text-destructive">{message}</p>
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
  const tagSuggestions = useTagNames()

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

  const normal = useFormValues(normalForm)
  const transfer = useFormValues(transferForm)
  const normalCurrency = currencyOf(accounts.data, normal.accountId)
  const sentCurrency = currencyOf(accounts.data, transfer.fromId)
  const receivedCurrency = currencyOf(accounts.data, transfer.toId)
  const isCrossCurrency =
    transfer.fromId !== null && transfer.toId !== null && sentCurrency !== receivedCurrency

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
        new_category: values.newCategory.length > 0 ? values.newCategory : undefined,
        notes: values.notes && values.notes.length > 0 ? values.notes : undefined,
        tags: values.tags.length > 0 ? values.tags : undefined,
        meta_id: values.type === "expense" ? values.metaId : null,
        recurring_id: values.type === "expense" ? values.settlesCharge : null,
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
        amount_received: isCrossCurrency
          ? (finiteOrNull(values.amountReceived) ?? undefined)
          : undefined,
        currency: sentCurrency,
        date: values.date,
        notes: values.notes && values.notes.length > 0 ? values.notes : undefined,
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
                    <Label htmlFor="tx-create-type">Tipo *</Label>
                    <Select
                      id="tx-create-type"
                      value={field.state.value as string}
                      onValueChange={(v) => {
                        if (!v) return
                        field.handleChange(v as never)
                        normalForm.setFieldValue("categoryId", null)
                        normalForm.setFieldValue("newCategory", "")
                        normalForm.setFieldValue("metaId", null)
                        normalForm.setFieldValue("settlesCharge", null)
                      }}
                      items={TYPE_ITEMS}
                    />
                  </div>
                )}
              </normalForm.Field>
              <normalForm.Field name="accountId">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label htmlFor="tx-create-account">Cuenta *</Label>
                    <EntitySelect
                      id="tx-create-account"
                      value={field.state.value as number | null}
                      onChange={(v) => field.handleChange(v as never)}
                      queryKey={qk.accounts(false)}
                      queryFn={() => listAccounts(false)}
                    />
                    <FieldError field={field} />
                  </div>
                )}
              </normalForm.Field>
              <normalForm.Field name="amount">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label htmlFor="tx-create-amount">Monto * ({normalCurrency})</Label>
                    <MoneyInput
                      id="tx-create-amount"
                      currency={normalCurrency}
                      value={finiteOrNull(field.state.value)}
                      onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                    />
                    <FieldError field={field} />
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
                  <CategoryField
                    id="tx-create-category"
                    isIncome={normal.type === "income"}
                    value={{
                      categoryId: field.state.value as number | null,
                      newCategory: normal.newCategory,
                    }}
                    onChange={(choice) => {
                      field.handleChange(choice.categoryId as never)
                      normalForm.setFieldValue("newCategory", choice.newCategory)
                      normalForm.setFieldValue("settlesCharge", null)
                    }}
                    error={fieldError(field)}
                  />
                )}
              </normalForm.Field>
              <normalForm.Subscribe
                selector={(state) => ({
                  type: state.values.type,
                  month: yearMonthOf(state.values.date),
                  metaId: state.values.metaId,
                  categoryId: state.values.categoryId,
                  settlesCharge: state.values.settlesCharge,
                })}
              >
                {({ type, month, metaId, categoryId, settlesCharge }) =>
                  type === "expense" && month !== null ? (
                    <>
                      <MetaField
                        id="tx-create-meta"
                        month={month}
                        value={metaId}
                        onChange={(chosen) => normalForm.setFieldValue("metaId", chosen)}
                      />
                      <SettlesChargeField
                        id="tx-create-settles"
                        month={month}
                        categoryId={categoryId}
                        value={settlesCharge}
                        onChange={(chosen) => normalForm.setFieldValue("settlesCharge", chosen)}
                      />
                    </>
                  ) : null
                }
              </normalForm.Subscribe>
              <normalForm.Field name="tags">
                {(field) => (
                  <TagChipsInput
                    value={field.state.value as string[]}
                    onChange={(tags) => field.handleChange(tags as never)}
                    suggestions={tagSuggestions}
                  />
                )}
              </normalForm.Field>
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
                    <FieldError field={field} />
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
                    <FieldError field={field} />
                  </div>
                )}
              </transferForm.Field>
              <transferForm.Field name="amount">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>
                      {isCrossCurrency ? "Monto enviado" : "Monto"} * ({sentCurrency})
                    </Label>
                    <MoneyInput
                      currency={sentCurrency}
                      value={finiteOrNull(field.state.value)}
                      onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                    />
                    <FieldError field={field} />
                  </div>
                )}
              </transferForm.Field>
              <transferForm.Field name="amountReceived">
                {(field) => (
                  <TransferReceivedField
                    active={isCrossCurrency}
                    sentCurrency={sentCurrency}
                    receivedCurrency={receivedCurrency}
                    sentCents={finiteOrNull(transfer.amount)}
                    receivedCents={finiteOrNull(field.state.value)}
                    onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                    errorMessage={fieldError(field)}
                  />
                )}
              </transferForm.Field>
              <transferForm.Field name="date">
                {(field) => <FormField field={field} label="Fecha" type="date" />}
              </transferForm.Field>
              <transferForm.Field name="notes">
                {(field) => <FormField field={field} label="Notas" />}
              </transferForm.Field>
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
