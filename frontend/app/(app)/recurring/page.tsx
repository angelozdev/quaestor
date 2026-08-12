"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { CategoryField } from "@/components/category-field"
import { CheckboxField } from "@/components/checkbox-field"
import { ConfirmDialog } from "@/components/confirm-dialog"
import { DataTable } from "@/components/data-table"
import { EntitySelect } from "@/components/entity-select"
import { FormField } from "@/components/form-field"
import { MoneyAmount } from "@/components/money-amount"
import { MoneyInput } from "@/components/money-input"
import { PageHeader } from "@/components/page-header"
import { HelpExample, HelpSection, ScreenHelp } from "@/components/screen-help"
import { StatusBadge } from "@/components/status-badge"
import { listAccounts } from "@/lib/api/accounts"
import { getFx } from "@/lib/api/fx"
import {
  createRecurring,
  deleteRecurring,
  listRecurring,
  restoreRecurring,
  skipRecurring,
  updateRecurring,
} from "@/lib/api/recurring"
import { ApiError, applyApiErrorsToForm, type IntervalUnit, type Recurring } from "@/lib/api/types"
import { hasEnded } from "@/lib/date"
import {
  amountForAccount,
  convertCents,
  currencyOf,
  formatCents,
  type StatedAmount,
} from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { useFormValues } from "@/lib/use-form-values"
import { useAmountBox } from "@/lib/use-stated-amount"
import { Badge, Button, Dialog, DialogPopup, DialogTitle, Input, Label, Select } from "@/ui"
import { PendingDatesDialog } from "./pending-dates-dialog"
import { type RecurringCreateValues, recurringCreateSchema } from "./recurring.schema"

const TYPE_ITEMS = [
  { value: "expense", label: "Gasto" },
  { value: "income", label: "Ingreso" },
]
const MODE_ITEMS = [
  { value: "auto", label: "Automático" },
  { value: "manual", label: "Manual" },
]
const UNIT_ITEMS = [
  { value: "day", label: "Día(s)" },
  { value: "week", label: "Semana(s)" },
  { value: "month", label: "Mes(es)" },
  { value: "year", label: "Año(s)" },
]
const CURRENCY_ITEMS = [
  { value: "COP", label: "Pesos (COP)" },
  { value: "USD", label: "Dólares (USD)" },
]

/**
 * The currency the price is stated in — the merchant's, not the account's
 * (ADR-0053).
 *
 * Picking one is the owner restating the figure he already wrote, so the box
 * holding it is told as well; otherwise a later account change would restate
 * from a currency he had already left behind.
 */
function PriceCurrencyField({
  id,
  value,
  onPick,
}: {
  id: string
  value: string
  onPick: (currency: string) => void
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>Moneda del precio *</Label>
      <Select id={id} value={value} onValueChange={(v) => v && onPick(v)} items={CURRENCY_ITEMS} />
    </div>
  )
}

const UNIT_SINGULAR: Record<IntervalUnit, string> = {
  day: "día",
  week: "semana",
  month: "mes",
  year: "año",
}
const UNIT_PLURAL: Record<IntervalUnit, string> = {
  day: "días",
  week: "semanas",
  month: "meses",
  year: "años",
}

function intervalLabel(unit: IntervalUnit, count: number): string {
  if (count === 1) return `Cada ${UNIT_SINGULAR[unit]}`
  return `Cada ${count} ${UNIT_PLURAL[unit]}`
}

const BLANK_CHARGE: RecurringCreateValues = {
  name: "",
  payee: "",
  amount: Number.NaN,
  currency: "COP",
  categoryId: null,
  newCategory: "",
  accountId: null,
  type: "expense",
  mode: "manual",
  intervalCount: 1,
  intervalUnit: "month",
  startDate: "",
  endDate: "",
}

/**
 * A blank charge that starts today.
 *
 * Held in state rather than rebuilt each render: a form compares the defaults it
 * is handed against the ones it holds, and a fresh object that no longer matches
 * what `reset` put there is taken as a new default and overwrites it — which is
 * how the edit dialog opened blank over the charge it was asked about.
 */
function chargeStartingToday(): RecurringCreateValues {
  return { ...BLANK_CHARGE, startDate: new Date().toISOString().slice(0, 10) }
}

/** A charge already registered, as the boxes that edit it. */
function boxesFor(charge: Recurring): RecurringCreateValues {
  return {
    name: charge.name,
    payee: charge.payee ?? "",
    amount: charge.amount,
    currency: charge.currency as RecurringCreateValues["currency"],
    categoryId: charge.category_id,
    newCategory: "",
    accountId: charge.account_id,
    type: charge.type,
    mode: charge.mode,
    intervalCount: charge.interval_count,
    intervalUnit: charge.interval_unit,
    startDate: charge.start_date,
    endDate: charge.end_date ?? "",
  }
}

/**
 * What picking an account proposes to the price boxes: the account's own
 * currency, and the figure restated in it.
 *
 * A proposal, never a decision — the price belongs to the merchant, so the owner
 * can put back the currency he was charged in and the figure he was charged
 * (ADR-0053, AC-13). Restating always reads the figure he stated, so a trip out
 * to another currency and back offers what the charge already held.
 */
function offerTheAccountsCurrency({
  accounts,
  chosen,
  stated,
  usdCop,
  setCurrency,
  offer,
}: {
  accounts: { id: number; currency: string }[] | undefined
  chosen: number | null
  stated: StatedAmount
  usdCop: number | null
  setCurrency: (currency: string) => void
  offer: (cents: number | null) => void
}) {
  const to = currencyOf(accounts, chosen)
  if (to === stated.currency) return
  setCurrency(to)
  if (stated.cents !== null) offer(amountForAccount(stated, to, usdCop))
}

/**
 * A charge's price, and what it comes to in the account that pays it.
 *
 * The price is the merchant's and is shown as stated; the converted figure is
 * today's reading of it, marked as approximate because it is (ADR-0031). With no
 * rate set there is nothing honest to add, so nothing is added — the price still
 * reads (AC-4).
 */
function RulePrice({
  charge,
  accounts,
  usdCop,
}: {
  charge: Recurring
  accounts: { id: number; currency: string }[] | undefined
  usdCop: number | null
}) {
  const settled = currencyOf(accounts, charge.account_id)
  const converted =
    settled === charge.currency
      ? null
      : convertCents(charge.amount, charge.currency, settled, usdCop)
  return (
    <span className="flex flex-col items-end">
      <MoneyAmount cents={charge.amount} currency={charge.currency} type={charge.type} />
      {converted !== null && (
        <span className="text-xs tabular-nums" style={{ color: "var(--muted-foreground)" }}>
          ≈ {formatCents(converted, settled)}
        </span>
      )}
    </span>
  )
}

const WHAT_A_RECURRING_CHARGE_IS = (
  <p>
    Un cobro recurrente es uno que vuelve solo — cada mes, cada año o cada cuantos días le digas. Lo
    registras una vez y la app lo espera por ti en <strong>Por pagar</strong>.
  </p>
)

/** What this screen is, said with the charges it is showing. */
function RecurringHelp({ items }: { items: Recurring[] | undefined }) {
  return (
    <>
      {WHAT_A_RECURRING_CHARGE_IS}
      {items !== undefined && items.length > 0 ? (
        <HelpSection lead="Los que tienes registrados:">
          {items.map((item) => (
            <li key={item.id}>
              {`${item.name} — cobra ${formatCents(item.amount, item.currency)} ${intervalLabel(
                item.interval_unit,
                item.interval_count,
              ).toLowerCase()}.`}
            </li>
          ))}
        </HelpSection>
      ) : (
        <HelpExample>
          <li>Por ejemplo: Netflix cobra $ 35.000 cada mes.</li>
        </HelpExample>
      )}
    </>
  )
}

/**
 * The dialog that edits one charge, mounted on the charge itself.
 *
 * Keyed by the row so every opening starts a form whose defaults are that
 * charge: a form seeded after the fact is overwritten by the defaults it was
 * declared with on the very next render.
 */
function EditChargeForm({ charge, onDone }: { charge: Recurring; onDone: () => void }) {
  const qc = useQueryClient()
  const accounts = useQuery({ queryKey: qk.accounts(false), queryFn: () => listAccounts(false) })
  const fx = useQuery({ queryKey: qk.fx(), queryFn: getFx })
  const usdCop = fx.data ? Number(fx.data.usd_cop) : null

  const editForm = useTanStackForm({
    defaultValues: boxesFor(charge),
    validators: { onChange: recurringCreateSchema },
    onSubmit: async ({ value }) => {
      update.mutate(value)
    },
  })

  const editValues = useFormValues(editForm)
  const editCurrency = editValues.currency
  const money = useAmountBox({ cents: charge.amount, currency: charge.currency }, (cents) =>
    editForm.setFieldValue("amount", cents ?? Number.NaN),
  )

  const update = useMutation({
    mutationFn: (values: RecurringCreateValues) =>
      updateRecurring(charge.id, {
        name: values.name,
        amount: values.amount,
        currency: values.currency,
        payee: values.payee && values.payee.length > 0 ? values.payee : undefined,
        category_id: values.categoryId,
        account_id: values.accountId ?? undefined,
        mode: values.mode,
        interval_unit: values.intervalUnit,
        interval_count: values.intervalCount,
        start_date: values.startDate,
        end_date: values.endDate ? values.endDate : null,
      }),
    onSuccess: () => {
      toast.success("Recurrente actualizado")
      invalidate(qc, "recurringWrite")
      onDone()
    },
    onError: (e: unknown) => {
      applyApiErrorsToForm(editForm, e)
      toast.error(e instanceof ApiError ? e.message : "Error")
    },
  })

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        e.stopPropagation()
        void editForm.handleSubmit()
      }}
      className="space-y-4"
    >
      <editForm.Field name="name">
        {(field) => <FormField field={field} label="Nombre" />}
      </editForm.Field>
      <div className="grid grid-cols-2 gap-3">
        <editForm.Field name="type">
          {() => (
            <div className="space-y-1.5">
              <Label>Tipo (no editable)</Label>
              <Select
                value={editValues.type}
                onValueChange={() => {}}
                items={TYPE_ITEMS}
                disabled
              />
            </div>
          )}
        </editForm.Field>
        <editForm.Field name="mode">
          {(field) => (
            <div className="space-y-1.5">
              <Label>Modo *</Label>
              <Select
                value={field.state.value as string}
                onValueChange={(v) => v && field.handleChange(v as never)}
                items={MODE_ITEMS}
              />
            </div>
          )}
        </editForm.Field>
      </div>
      <editForm.Field name="accountId">
        {(field) => (
          <div className="space-y-1.5">
            <Label>Cuenta *</Label>
            <EntitySelect
              value={field.state.value as number | null}
              onChange={(v) => {
                const chosen = v as number | null
                field.handleChange(chosen as never)
                offerTheAccountsCurrency({
                  accounts: accounts.data,
                  chosen,
                  stated: money.stated,
                  usdCop,
                  setCurrency: (c) => editForm.setFieldValue("currency", c as never),
                  offer: money.offer,
                })
              }}
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
      </editForm.Field>
      <div className="grid grid-cols-[1fr_auto] gap-3">
        <editForm.Field name="amount">
          {(field) => (
            <div className="space-y-1.5">
              <Label>Monto * ({editCurrency})</Label>
              <MoneyInput
                currency={editCurrency}
                value={
                  typeof field.state.value === "number" && Number.isFinite(field.state.value)
                    ? (field.state.value as number)
                    : null
                }
                onChange={(cents) => money.write(cents, editCurrency)}
              />
              {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                <p className="text-xs text-destructive">
                  {String((field.state.meta.errors[0] as { message?: string })?.message)}
                </p>
              )}
            </div>
          )}
        </editForm.Field>
        <editForm.Field name="currency">
          {(field) => (
            <PriceCurrencyField
              id="recurring-edit-currency"
              value={field.state.value as string}
              onPick={(currency) => {
                field.handleChange(currency as never)
                money.write(money.stated.cents, currency)
              }}
            />
          )}
        </editForm.Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <editForm.Field name="intervalCount">
          {(field) => (
            <FormField field={field} label="Cada (cantidad)" type="number" min={1} valueAsNumber />
          )}
        </editForm.Field>
        <editForm.Field name="intervalUnit">
          {(field) => (
            <div className="space-y-1.5">
              <Label>Unidad *</Label>
              <Select
                value={field.state.value as string}
                onValueChange={(v) => v && field.handleChange(v as never)}
                items={UNIT_ITEMS}
              />
              {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                <p className="text-xs text-destructive">
                  {String((field.state.meta.errors[0] as { message?: string })?.message)}
                </p>
              )}
            </div>
          )}
        </editForm.Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <editForm.Field name="startDate">
          {(field) => <FormField field={field} label="Inicio" type="date" />}
        </editForm.Field>
        <editForm.Field name="endDate">
          {(field) => <FormField field={field} label="Fin (opcional)" type="date" />}
        </editForm.Field>
      </div>
      <editForm.Field name="categoryId">
        {(field) => (
          <CategoryField
            id="recurring-edit-category"
            allowCreate={false}
            isIncome={editValues.type === "income"}
            value={{
              categoryId: field.state.value as number | null,
              newCategory: editValues.newCategory,
            }}
            onChange={(choice) => {
              field.handleChange(choice.categoryId as never)
              editForm.setFieldValue("newCategory", choice.newCategory)
            }}
            error={(field.state.meta.errors[0] as { message?: string } | undefined)?.message}
          />
        )}
      </editForm.Field>
      <editForm.Field name="payee">
        {(field) => <FormField field={field} label="Beneficiario" />}
      </editForm.Field>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={() => onDone()}>
          Cancelar
        </Button>
        <Button type="submit" disabled={update.isPending || editForm.state.isSubmitting}>
          {update.isPending || editForm.state.isSubmitting ? "…" : "Guardar"}
        </Button>
      </div>
    </form>
  )
}

export default function RecurringPage() {
  const qc = useQueryClient()

  const [showInactive, setShowInactive] = useState(false)
  const list = useQuery({
    queryKey: qk.recurring(showInactive ? undefined : true),
    queryFn: () => listRecurring(showInactive ? undefined : true),
  })

  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Recurring | null>(null)
  const [deleting, setDeleting] = useState<Recurring | null>(null)
  const [answering, setAnswering] = useState<Recurring | null>(null)

  const [createDefaults] = useState(chargeStartingToday)

  const createForm = useTanStackForm({
    defaultValues: createDefaults,
    validators: { onChange: recurringCreateSchema },
    onSubmit: async ({ value }) => {
      create.mutate(value)
    },
  })

  const accounts = useQuery({ queryKey: qk.accounts(false), queryFn: () => listAccounts(false) })
  const fx = useQuery({ queryKey: qk.fx(), queryFn: getFx })
  const usdCop = fx.data ? Number(fx.data.usd_cop) : null
  const createValues = useFormValues(createForm)
  const createCurrency = createValues.currency
  const createMoney = useAmountBox({ cents: null, currency: BLANK_CHARGE.currency }, (cents) =>
    createForm.setFieldValue("amount", cents ?? Number.NaN),
  )

  /**
   * Empty the form and the price box together.
   *
   * The create dialog hangs off the screen rather than off a charge, so it
   * outlives the one just saved — and a box emptied on its own would still be
   * holding what the owner stated last time, ready to offer it converted the
   * next time he picks an account.
   */
  function startANewCharge() {
    createForm.reset(createDefaults)
    createMoney.write(null, BLANK_CHARGE.currency)
  }

  const [skipping, setSkipping] = useState<Recurring | null>(null)
  const [skipDate, setSkipDate] = useState("")

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")
  const done = (msg: string) => {
    toast.success(msg)
    invalidate(qc, "recurringWrite")
  }

  const create = useMutation({
    mutationFn: (values: RecurringCreateValues) => {
      return createRecurring({
        name: values.name,
        type: values.type,
        mode: values.mode,
        amount: values.amount,
        account_id: values.accountId as number,
        interval_unit: values.intervalUnit,
        interval_count: values.intervalCount,
        start_date: values.startDate,
        end_date: values.endDate ? values.endDate : null,
        currency: values.currency,
        category_id: values.categoryId,
        new_category: values.newCategory.length > 0 ? values.newCategory : undefined,
        payee: values.payee && values.payee.length > 0 ? values.payee : undefined,
      })
    },
    onSuccess: () => {
      done("Recurrente creado")
      setCreating(false)
      startANewCharge()
    },
    onError: (e: unknown) => {
      applyApiErrorsToForm(createForm, e)
      onErr(e)
    },
  })

  const remove = useMutation({
    mutationFn: () => {
      if (!deleting) throw new Error("deleting recurring is required")
      return deleteRecurring(deleting.id)
    },
    onSuccess: () => {
      done("Recurrente desactivado")
      setDeleting(null)
    },
    onError: onErr,
  })

  const restore = useMutation({
    mutationFn: (r: Recurring) => restoreRecurring(r.id),
    onSuccess: () => done("Recurrente restaurado"),
    onError: onErr,
  })

  const skip = useMutation({
    mutationFn: () => {
      if (!skipping) throw new Error("skipping recurring is required")
      return skipRecurring(skipping.id, skipDate)
    },
    onSuccess: () => {
      done("Ocurrencia omitida")
      setSkipping(null)
      setSkipDate("")
    },
    onError: onErr,
  })

  return (
    <div className="space-y-10">
      <PageHeader
        title="Recurrentes"
        action={<Button onClick={() => setCreating(true)}>Nuevo</Button>}
        help={
          <ScreenHelp screen="Recurrentes">
            <RecurringHelp items={list.data} />
          </ScreenHelp>
        }
      />

      <div className="space-y-3">
        <CheckboxField
          id="show-inactive"
          label="Mostrar inactivos"
          checked={showInactive}
          onCheckedChange={setShowInactive}
        />

        <DataTable
          rows={list.data}
          rowKey={(r) => r.id}
          isLoading={list.isLoading}
          isError={list.isError}
          onRetry={() => list.refetch()}
          columns={[
            {
              key: "name",
              header: "Nombre",
              render: (r) => (
                <span className="flex items-center gap-2 font-medium">
                  {r.name}
                  {!r.active && <StatusBadge kind="archived" value={true} />}
                  {r.active && hasEnded(r.end_date) && <Badge variant="ghost">Terminada</Badge>}
                </span>
              ),
            },
            {
              key: "interval",
              header: "Frecuencia",
              render: (r) => (
                <span style={{ color: "var(--muted-foreground)" }}>
                  {intervalLabel(r.interval_unit, r.interval_count)}
                </span>
              ),
            },
            {
              key: "mode",
              header: "Modo",
              render: (r) => <StatusBadge kind="mode" value={r.mode} />,
            },
            {
              key: "amount",
              header: "Monto",
              align: "right",
              render: (r) => <RulePrice charge={r} accounts={accounts.data} usdCop={usdCop} />,
            },
          ]}
          actionsAs="inline"
          actions={[
            {
              label: "Editar",
              show: (r) => r.active,
              onClick: (r) => setEditing(r),
            },
            { label: "Omitir", show: (r) => r.active, onClick: (r) => setSkipping(r) },
            { label: "Fechas pendientes", show: (r) => r.active, onClick: (r) => setAnswering(r) },
            {
              label: "Eliminar",
              show: (r) => r.active,
              variant: "destructive",
              onClick: (r) => setDeleting(r),
            },
            {
              label: "Restaurar",
              show: (r) => !r.active,
              disabled: restore.isPending,
              onClick: (r) => restore.mutate(r),
            },
          ]}
          emptyMessage="Todavía no tienes cobros recurrentes."
          emptyDescription={WHAT_A_RECURRING_CHARGE_IS}
          emptyAction={{ label: "Crear el primero", onClick: () => setCreating(true) }}
        />
      </div>

      {/* Create dialog */}
      <Dialog open={creating} onOpenChange={setCreating}>
        <DialogPopup className="max-w-lg">
          <DialogTitle>Nuevo recurrente</DialogTitle>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              e.stopPropagation()
              void createForm.handleSubmit()
            }}
            className="space-y-4"
          >
            <createForm.Field name="name">
              {(field) => <FormField field={field} label="Nombre" />}
            </createForm.Field>
            <div className="grid grid-cols-2 gap-3">
              <createForm.Field name="type">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label htmlFor="recurring-create-type">Tipo *</Label>
                    <Select
                      id="recurring-create-type"
                      value={field.state.value as string}
                      onValueChange={(v) => {
                        if (!v) return
                        field.handleChange(v as never)
                        createForm.setFieldValue("categoryId", null)
                        createForm.setFieldValue("newCategory", "")
                      }}
                      items={TYPE_ITEMS}
                    />
                  </div>
                )}
              </createForm.Field>
              <createForm.Field name="mode">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Modo *</Label>
                    <Select
                      value={field.state.value as string}
                      onValueChange={(v) => v && field.handleChange(v as never)}
                      items={MODE_ITEMS}
                    />
                  </div>
                )}
              </createForm.Field>
            </div>
            <createForm.Field name="accountId">
              {(field) => (
                <div className="space-y-1.5">
                  <Label>Cuenta *</Label>
                  <EntitySelect
                    value={field.state.value as number | null}
                    onChange={(v) => {
                      const chosen = v as number | null
                      field.handleChange(chosen as never)
                      offerTheAccountsCurrency({
                        accounts: accounts.data,
                        chosen,
                        stated: createMoney.stated,
                        usdCop,
                        setCurrency: (c) => createForm.setFieldValue("currency", c as never),
                        offer: createMoney.offer,
                      })
                    }}
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
            </createForm.Field>
            <div className="grid grid-cols-[1fr_auto] gap-3">
              <createForm.Field name="amount">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Monto * ({createCurrency})</Label>
                    <MoneyInput
                      currency={createCurrency}
                      value={
                        typeof field.state.value === "number" && Number.isFinite(field.state.value)
                          ? (field.state.value as number)
                          : null
                      }
                      onChange={(cents) => createMoney.write(cents, createCurrency)}
                    />
                    {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                      <p className="text-xs text-destructive">
                        {String((field.state.meta.errors[0] as { message?: string })?.message)}
                      </p>
                    )}
                  </div>
                )}
              </createForm.Field>
              <createForm.Field name="currency">
                {(field) => (
                  <PriceCurrencyField
                    id="recurring-create-currency"
                    value={field.state.value as string}
                    onPick={(currency) => {
                      field.handleChange(currency as never)
                      createMoney.write(createMoney.stated.cents, currency)
                    }}
                  />
                )}
              </createForm.Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <createForm.Field name="intervalCount">
                {(field) => (
                  <FormField
                    field={field}
                    label="Cada (cantidad)"
                    type="number"
                    min={1}
                    valueAsNumber
                  />
                )}
              </createForm.Field>
              <createForm.Field name="intervalUnit">
                {(field) => (
                  <div className="space-y-1.5">
                    <Label>Unidad *</Label>
                    <Select
                      value={field.state.value as string}
                      onValueChange={(v) => v && field.handleChange(v as never)}
                      items={UNIT_ITEMS}
                    />
                    {(field.state.meta.errors[0] as { message?: string } | undefined)?.message && (
                      <p className="text-xs text-destructive">
                        {String((field.state.meta.errors[0] as { message?: string })?.message)}
                      </p>
                    )}
                  </div>
                )}
              </createForm.Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <createForm.Field name="startDate">
                {(field) => <FormField field={field} label="Inicio" type="date" />}
              </createForm.Field>
              <createForm.Field name="endDate">
                {(field) => <FormField field={field} label="Fin (opcional)" type="date" />}
              </createForm.Field>
            </div>
            <createForm.Field name="categoryId">
              {(field) => (
                <CategoryField
                  id="recurring-create-category"
                  isIncome={createValues.type === "income"}
                  value={{
                    categoryId: field.state.value as number | null,
                    newCategory: createValues.newCategory,
                  }}
                  onChange={(choice) => {
                    field.handleChange(choice.categoryId as never)
                    createForm.setFieldValue("newCategory", choice.newCategory)
                  }}
                  error={(field.state.meta.errors[0] as { message?: string } | undefined)?.message}
                />
              )}
            </createForm.Field>
            <createForm.Field name="payee">
              {(field) => <FormField field={field} label="Beneficiario" />}
            </createForm.Field>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setCreating(false)}>
                Cancelar
              </Button>
              <Button type="submit" disabled={create.isPending || createForm.state.isSubmitting}>
                {create.isPending || createForm.state.isSubmitting ? "…" : "Crear"}
              </Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>

      {/* Edit dialog */}
      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogPopup className="max-w-lg">
          <DialogTitle>Editar recurrente</DialogTitle>
          {editing && (
            <EditChargeForm key={editing.id} charge={editing} onDone={() => setEditing(null)} />
          )}
        </DialogPopup>
      </Dialog>

      {/* Skip dialog */}
      <Dialog open={skipping !== null} onOpenChange={(o) => !o && setSkipping(null)}>
        <DialogPopup className="max-w-sm">
          <DialogTitle>Omitir ocurrencia</DialogTitle>
          {skipping && (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                if (skipDate) skip.mutate()
              }}
              className="space-y-4"
            >
              <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
                Indica la fecha de la ocurrencia de &quot;{skipping.name}&quot; que quieres omitir.
              </p>
              <div className="space-y-1.5">
                <Label>Fecha de la ocurrencia *</Label>
                <Input type="date" value={skipDate} onChange={(e) => setSkipDate(e.target.value)} />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setSkipping(null)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={!skipDate || skip.isPending}>
                  {skip.isPending ? "…" : "Omitir"}
                </Button>
              </div>
            </form>
          )}
        </DialogPopup>
      </Dialog>

      {answering && (
        <PendingDatesDialog recurring={answering} onOpenChange={(o) => !o && setAnswering(null)} />
      )}

      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Eliminar recurrente"
        description={`Se desactivará "${deleting?.name}". Las ocurrencias ya registradas se mantienen. Puedes restaurarlo luego.`}
        confirmLabel="Eliminar"
        destructive
        pending={remove.isPending}
        onConfirm={() => deleting && remove.mutate()}
      />
    </div>
  )
}
