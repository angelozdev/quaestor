"use client"

import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Controller, useForm } from "react-hook-form"
import { toast } from "sonner"
import { z } from "zod"
import { EntitySelect } from "@/components/entity-select"
import { FormField } from "@/components/form-field"
import { MoneyInput } from "@/components/money-input"
import { listAccounts } from "@/lib/api/accounts"
import { listCategories } from "@/lib/api/categories"
import { createTransaction, createTransfer as createTransferApi } from "@/lib/api/transactions"
import { type Account, ApiError } from "@/lib/api/types"
import { invalidate, qk } from "@/lib/query"
import { messages } from "@/lib/schemas/messages"
import { fxRate, isoDate, optionalString, positiveCents } from "@/lib/schemas/primitives"
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

function currencyOf(accounts: Account[] | undefined, id: number | null): string {
  if (id === null) return "COP"
  return accounts?.find((a) => a.id === id)?.currency ?? "COP"
}

// Normal tab: expense/income transaction. The category field is an ID
// (number | null) selected via EntitySelect, matching the existing UI.
const txNormalSchema = z
  .object({
    type: z.enum(["expense", "income"], {
      errorMap: () => ({ message: messages.opcionInvalida }),
    }),
    accountId: z.number().nullable(),
    amount: positiveCents,
    categoryId: z.number().nullable(),
    date: isoDate,
    payee: z.string().trim().max(500, "Máximo 500 caracteres").optional().or(z.literal("")),
    fxRate: fxRate.optional().or(z.literal(Number.NaN)),
    notes: optionalString,
  })
  .refine((d) => d.accountId !== null, {
    message: "Requerido",
    path: ["accountId"],
  })
type TxNormalValues = z.infer<typeof txNormalSchema>

// Transfer tab: between two accounts. Amount/date/from/to required.
const txTransferSchema = z
  .object({
    fromId: z.number().nullable(),
    toId: z.number().nullable(),
    amount: positiveCents,
    date: isoDate,
    fxRate: fxRate.optional().or(z.literal(Number.NaN)),
    notes: optionalString,
  })
  .refine((d) => d.fromId !== null, {
    message: "Requerido",
    path: ["fromId"],
  })
  .refine((d) => d.toId !== null, {
    message: "Requerido",
    path: ["toId"],
  })
type TxTransferValues = z.infer<typeof txTransferSchema>

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

  const normalForm = useForm<TxNormalValues>({
    resolver: zodResolver(txNormalSchema),
    defaultValues: {
      type: "expense",
      accountId: null,
      amount: Number.NaN,
      categoryId: null,
      date: new Date().toISOString().slice(0, 10),
      payee: "",
      fxRate: Number.NaN,
      notes: "",
    },
  })

  const transferForm = useForm<TxTransferValues>({
    resolver: zodResolver(txTransferSchema),
    defaultValues: {
      fromId: null,
      toId: null,
      amount: Number.NaN,
      date: new Date().toISOString().slice(0, 10),
      fxRate: Number.NaN,
      notes: "",
    },
  })

  const normalCurrency = currencyOf(accounts.data, normalForm.watch("accountId"))
  const transferCurrency = currencyOf(accounts.data, transferForm.watch("fromId"))

  function resetForms() {
    normalForm.reset({
      type: "expense",
      accountId: null,
      amount: Number.NaN,
      categoryId: null,
      date: new Date().toISOString().slice(0, 10),
      payee: "",
      fxRate: Number.NaN,
      notes: "",
    })
    transferForm.reset({
      fromId: null,
      toId: null,
      amount: Number.NaN,
      date: new Date().toISOString().slice(0, 10),
      fxRate: Number.NaN,
      notes: "",
    })
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
    onError: onErr,
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
    onError: onErr,
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
              onSubmit={normalForm.handleSubmit((values) => createNormal.mutate(values))}
              className="space-y-4 pt-2"
            >
              <Controller
                control={normalForm.control}
                name="type"
                render={({ field }) => (
                  <div className="space-y-1.5">
                    <Label>Tipo *</Label>
                    <Select
                      value={field.value}
                      onValueChange={(v) => field.onChange(v)}
                      items={TYPE_ITEMS}
                    />
                  </div>
                )}
              />
              <Controller
                control={normalForm.control}
                name="accountId"
                render={({ field, fieldState: { error } }) => (
                  <div className="space-y-1.5">
                    <Label>Cuenta *</Label>
                    <EntitySelect
                      value={field.value}
                      onChange={field.onChange}
                      queryKey={qk.accounts(false)}
                      queryFn={() => listAccounts(false)}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )}
              />
              <Controller
                control={normalForm.control}
                name="amount"
                render={({ field, fieldState: { error } }) => (
                  <div className="space-y-1.5">
                    <Label>Monto * ({normalCurrency})</Label>
                    <MoneyInput
                      currency={normalCurrency}
                      value={
                        typeof field.value === "number" && Number.isFinite(field.value)
                          ? field.value
                          : null
                      }
                      onChange={(cents) => field.onChange(cents ?? Number.NaN)}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )}
              />
              <FormField control={normalForm.control} name="date" label="Fecha" type="date" />
              <FormField control={normalForm.control} name="payee" label="Beneficiario" />
              <Controller
                control={normalForm.control}
                name="categoryId"
                render={({ field, fieldState: { error } }) => (
                  <div className="space-y-1.5">
                    <Label>Categoría</Label>
                    <EntitySelect
                      value={field.value}
                      onChange={field.onChange}
                      queryKey={qk.categories(false)}
                      queryFn={() => listCategories(false)}
                      allowNullLabel="Sin categoría"
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )}
              />
              {normalCurrency !== "COP" && (
                <FormField
                  control={normalForm.control}
                  name="fxRate"
                  label="Tasa USD→COP (opcional)"
                  type="number"
                  placeholder="Se resuelve sola si la dejas vacía"
                  valueAsNumber
                />
              )}
              <FormField control={normalForm.control} name="notes" label="Notas" />
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={createNormal.isPending}>
                  {createNormal.isPending ? "…" : "Crear"}
                </Button>
              </div>
            </form>
          </TabsContent>

          <TabsContent value="transfer">
            <form
              onSubmit={transferForm.handleSubmit((values) => createTransfer.mutate(values))}
              className="space-y-4 pt-2"
            >
              <Controller
                control={transferForm.control}
                name="fromId"
                render={({ field, fieldState: { error } }) => (
                  <div className="space-y-1.5">
                    <Label>Desde *</Label>
                    <EntitySelect
                      value={field.value}
                      onChange={field.onChange}
                      queryKey={qk.accounts(false)}
                      queryFn={() => listAccounts(false)}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )}
              />
              <Controller
                control={transferForm.control}
                name="toId"
                render={({ field, fieldState: { error } }) => (
                  <div className="space-y-1.5">
                    <Label>Hacia *</Label>
                    <EntitySelect
                      value={field.value}
                      onChange={field.onChange}
                      queryKey={qk.accounts(false)}
                      queryFn={() => listAccounts(false)}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )}
              />
              <Controller
                control={transferForm.control}
                name="amount"
                render={({ field, fieldState: { error } }) => (
                  <div className="space-y-1.5">
                    <Label>Monto * ({transferCurrency})</Label>
                    <MoneyInput
                      currency={transferCurrency}
                      value={
                        typeof field.value === "number" && Number.isFinite(field.value)
                          ? field.value
                          : null
                      }
                      onChange={(cents) => field.onChange(cents ?? Number.NaN)}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )}
              />
              <FormField control={transferForm.control} name="date" label="Fecha" type="date" />
              {transferCurrency !== "COP" && (
                <FormField
                  control={transferForm.control}
                  name="fxRate"
                  label="Tasa USD→COP (opcional)"
                  type="number"
                  valueAsNumber
                />
              )}
              <FormField control={transferForm.control} name="notes" label="Notas" />
              <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                Ambas cuentas deben tener la misma moneda.
              </p>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={createTransfer.isPending}>
                  {createTransfer.isPending ? "…" : "Crear"}
                </Button>
              </div>
            </form>
          </TabsContent>
        </Tabs>
      </DialogPopup>
    </Dialog>
  )
}
