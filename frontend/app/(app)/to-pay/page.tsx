"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { endOfMonth, endOfWeek, format, startOfMonth, startOfWeek } from "date-fns"
import { useState } from "react"
import { toast } from "sonner"
import { CategoryField } from "@/components/category-field"
import { EmptyState } from "@/components/empty-state"
import { EntitySelect } from "@/components/entity-select"
import { ErrorState } from "@/components/error-state"
import { FormField } from "@/components/form-field"
import { Section } from "@/components/ledger"
import { MetaField } from "@/components/meta-field"
import { MoneyAmount } from "@/components/money-amount"
import { MoneyInput } from "@/components/money-input"
import { PageHeader } from "@/components/page-header"
import { type Scope, ScopePicker } from "@/components/scope-picker"
import { ScreenHelp } from "@/components/screen-help"
import { listAccounts } from "@/lib/api/accounts"
import { getFx } from "@/lib/api/fx"
import { confirmPayment, planPayment, skipPlanned, toPay } from "@/lib/api/planned"
import { ApiError, applyApiErrorsToForm, type Transaction } from "@/lib/api/types"
import { formatDate, yearMonthOf } from "@/lib/date"
import { amountForAccount, currencyForAccount, currencyOf, formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { useFormValues } from "@/lib/use-form-values"
import { useStatedAmount } from "@/lib/use-stated-amount"
import { Badge, Button, Dialog, DialogPopup, DialogTitle, Input, Label, Textarea } from "@/ui"
import { type PlanPaymentValues, planPaymentSchema } from "./to-pay.schema"

function windowFor(scope: Scope) {
  const now = new Date()
  const [since, until] =
    scope === "week"
      ? [startOfWeek(now, { weekStartsOn: 1 }), endOfWeek(now, { weekStartsOn: 1 })]
      : [startOfMonth(now), endOfMonth(now)]
  return { since: format(since, "yyyy-MM-dd"), until: format(until, "yyyy-MM-dd") }
}

const WHAT_IS_PENDING = (
  <p>
    Aquí aparecen los cobros que ya vencieron o vencen dentro del periodo y todavía no has pagado.
  </p>
)

const TO_PAY_HELP = (
  <>
    {WHAT_IS_PENDING}
    <p>
      Salen de dos sitios: los cobros recurrentes que registraste, y los pagos sueltos que planeas
      con <strong>Planear pago</strong>. Confirmas uno cuando lo pagas y lo omites cuando ese cobro
      no llegó.
    </p>
  </>
)

/**
 * The month a debt belongs to is the month it is due, so that is the month
 * whose metas it may point at. A form with no date yet offers this month's,
 * which is what the picker showed before the owner said anything.
 */
function monthOf(dueDate: string): string {
  return yearMonthOf(dueDate) ?? format(new Date(), "yyyy-MM")
}

const PLAN_DEFAULTS: PlanPaymentValues = {
  payee: "",
  accountId: null,
  amount: Number.NaN,
  dueDate: "",
  categoryId: null,
  newCategory: "",
  metaId: null,
  notes: undefined,
}

export default function ToPayPage() {
  const qc = useQueryClient()
  const [scope, setScope] = useState<Scope>("week")
  const { since, until } = windowFor(scope)

  const [confirming, setConfirming] = useState<Transaction | null>(null)
  const confirmMoney = useStatedAmount({ cents: null, currency: "COP" })
  const [cDate, setCDate] = useState("")
  const [cAccountId, setCAccountId] = useState<number | null>(null)

  const [planning, setPlanning] = useState(false)

  const planForm = useTanStackForm({
    defaultValues: PLAN_DEFAULTS,
    validators: { onChange: planPaymentSchema },
    onSubmit: async ({ value }) => {
      plan.mutate(value)
    },
  })

  const list = useQuery({ queryKey: qk.toPay(since, until), queryFn: () => toPay(since, until) })
  const accounts = useQuery({ queryKey: qk.accounts(false), queryFn: () => listAccounts(false) })
  const fx = useQuery({ queryKey: qk.fx(), queryFn: getFx })
  const usdCop = fx.data ? Number(fx.data.usd_cop) : null
  const confirmCurrency = currencyForAccount(confirming, accounts.data, cAccountId)

  const planValues = useFormValues(planForm)
  const planCurrency = currencyOf(accounts.data, planValues.accountId)

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")
  const done = (msg: string) => {
    toast.success(msg)
    invalidate(qc, "plannedWrite")
  }

  const confirm = useMutation({
    mutationFn: () => {
      if (!confirming) throw new Error("confirming transaction is required")
      return confirmPayment(confirming.id, {
        amount: confirmMoney.amount ?? undefined,
        date: cDate || undefined,
        account_id: cAccountId ?? undefined,
      })
    },
    onSuccess: () => {
      done("Pago confirmado")
      setConfirming(null)
    },
    onError: onErr,
  })
  const skip = useMutation({
    mutationFn: (id: number) => skipPlanned(id),
    onSuccess: () => done("Pago omitido"),
    onError: onErr,
  })
  const plan = useMutation({
    mutationFn: (values: PlanPaymentValues) => {
      return planPayment({
        payee: values.payee,
        amount: values.amount,
        due_date: values.dueDate,
        account_id: values.accountId as number,
        currency: planCurrency,
        category_id: values.categoryId,
        new_category: values.newCategory.length > 0 ? values.newCategory : undefined,
        meta_id: values.metaId,
        notes: values.notes && values.notes.length > 0 ? values.notes : undefined,
      })
    },
    onSuccess: () => {
      done("Pago planeado")
      setPlanning(false)
      planForm.reset(PLAN_DEFAULTS)
    },
    onError: (e: unknown) => {
      applyApiErrorsToForm(planForm, e)
      onErr(e)
    },
  })

  function openConfirm(item: Transaction) {
    setConfirming(item)
    confirmMoney.write(item.amount, item.currency)
    setCDate(item.date)
    setCAccountId(item.account_id)
  }

  return (
    <div className="space-y-10">
      <PageHeader
        title="Por pagar"
        action={
          <Button
            onClick={() => {
              planForm.reset(PLAN_DEFAULTS)
              setPlanning(true)
            }}
          >
            Planear pago
          </Button>
        }
        help={<ScreenHelp screen="Por pagar">{TO_PAY_HELP}</ScreenHelp>}
      />

      <div className="space-y-3">
        <ScopePicker scope={scope} onPick={setScope} />

        {list.isError && (
          <ErrorState message="No se pudo cargar lo pendiente" onRetry={() => list.refetch()} />
        )}

        {list.data && (
          <p className="text-[2.5rem] font-semibold leading-[1.05] tabular-nums tracking-tight">
            {formatCents(list.data.total_base, "COP")}
          </p>
        )}
      </div>

      {list.data &&
        (list.data.overdue.length === 0 && list.data.upcoming.length === 0 ? (
          <EmptyState message="Nada pendiente en este periodo." description={WHAT_IS_PENDING} />
        ) : (
          <div className="space-y-10">
            {list.data.overdue.length > 0 && (
              <Section
                label="Vencidos"
                badge={<Badge variant="destructive">{list.data.overdue.length}</Badge>}
              >
                <ul className="divide-y" style={{ borderColor: "var(--border)" }}>
                  {list.data.overdue.map((item) => (
                    <ToPayRow
                      key={item.id}
                      item={item}
                      isOverdueRow
                      onConfirm={() => openConfirm(item)}
                      onSkip={() => skip.mutate(item.id)}
                      skipPending={skip.isPending}
                    />
                  ))}
                </ul>
              </Section>
            )}

            {list.data.upcoming.length > 0 && (
              <Section label={scope === "week" ? "Esta semana" : "Este mes"}>
                <ul className="divide-y" style={{ borderColor: "var(--border)" }}>
                  {list.data.upcoming.map((item) => (
                    <ToPayRow
                      key={item.id}
                      item={item}
                      isOverdueRow={false}
                      onConfirm={() => openConfirm(item)}
                      onSkip={() => skip.mutate(item.id)}
                      skipPending={skip.isPending}
                    />
                  ))}
                </ul>
              </Section>
            )}
          </div>
        ))}

      {/* Confirm dialog */}
      <Dialog open={confirming !== null} onOpenChange={(o) => !o && setConfirming(null)}>
        <DialogPopup className="max-w-sm">
          <DialogTitle>Confirmar pago</DialogTitle>
          {confirming && (
            <form
              onSubmit={(e) => {
                e.preventDefault()
                confirm.mutate()
              }}
              className="space-y-4"
            >
              <div className="space-y-1.5">
                <Label htmlFor="confirm-account">Cuenta</Label>
                <EntitySelect
                  id="confirm-account"
                  value={cAccountId}
                  onChange={(chosen) => {
                    const next = chosen as number | null
                    const to = currencyOf(accounts.data, next)
                    setCAccountId(next)
                    if (to !== confirmCurrency) {
                      confirmMoney.offer(amountForAccount(confirmMoney.stated, to, usdCop))
                    }
                  }}
                  queryKey={qk.accounts(false)}
                  queryFn={() => listAccounts(false)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="confirm-amount">Monto real ({confirmCurrency})</Label>
                <MoneyInput
                  id="confirm-amount"
                  currency={confirmCurrency}
                  value={confirmMoney.amount}
                  onChange={(cents) => confirmMoney.write(cents, confirmCurrency)}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="confirm-date">Fecha</Label>
                <Input
                  id="confirm-date"
                  type="date"
                  value={cDate}
                  onChange={(e) => setCDate(e.target.value)}
                />
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={() => setConfirming(null)}>
                  Cancelar
                </Button>
                <Button type="submit" disabled={confirm.isPending}>
                  {confirm.isPending ? "…" : "Confirmar"}
                </Button>
              </div>
            </form>
          )}
        </DialogPopup>
      </Dialog>

      {/* Plan one-off dialog */}
      <Dialog
        open={planning}
        onOpenChange={(o) => {
          if (!o) {
            setPlanning(false)
            planForm.reset(PLAN_DEFAULTS)
          }
        }}
      >
        <DialogPopup>
          <DialogTitle>Planear pago</DialogTitle>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              e.stopPropagation()
              void planForm.handleSubmit()
            }}
            className="space-y-4"
          >
            <planForm.Field name="payee">
              {(field) => <FormField field={field} label="Beneficiario" />}
            </planForm.Field>
            <planForm.Field name="accountId">
              {(field) => {
                const error = field.state.meta.errors[0] as { message?: string } | undefined
                return (
                  <div className="space-y-1.5">
                    <Label>Cuenta *</Label>
                    <EntitySelect
                      value={field.state.value as number | null}
                      onChange={(v) => field.handleChange(v as never)}
                      queryKey={qk.accounts(false)}
                      queryFn={() => listAccounts(false)}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )
              }}
            </planForm.Field>
            <planForm.Field name="amount">
              {(field) => {
                const error = field.state.meta.errors[0] as { message?: string } | undefined
                return (
                  <div className="space-y-1.5">
                    <Label>Monto * ({planCurrency})</Label>
                    <MoneyInput
                      currency={planCurrency}
                      value={
                        typeof field.state.value === "number" && Number.isFinite(field.state.value)
                          ? (field.state.value as number)
                          : null
                      }
                      onChange={(cents) => field.handleChange((cents ?? Number.NaN) as never)}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )
              }}
            </planForm.Field>
            <planForm.Field name="dueDate">
              {(field) => <FormField field={field} label="Fecha de vencimiento" type="date" />}
            </planForm.Field>
            <planForm.Field name="categoryId">
              {(field) => {
                const error = field.state.meta.errors[0] as { message?: string } | undefined
                return (
                  <CategoryField
                    id="plan-category"
                    isIncome={false}
                    value={{
                      categoryId: field.state.value as number | null,
                      newCategory: planValues.newCategory,
                    }}
                    onChange={(choice) => {
                      field.handleChange(choice.categoryId as never)
                      planForm.setFieldValue("newCategory", choice.newCategory)
                    }}
                    error={error?.message}
                  />
                )
              }}
            </planForm.Field>
            <planForm.Subscribe
              selector={(state) => ({
                month: monthOf(state.values.dueDate),
                metaId: state.values.metaId,
              })}
            >
              {({ month, metaId }) => (
                <MetaField
                  id="plan-meta"
                  month={month}
                  value={metaId}
                  onChange={(chosen) => planForm.setFieldValue("metaId", chosen)}
                />
              )}
            </planForm.Subscribe>
            <planForm.Field name="notes">
              {(field) => {
                const error = field.state.meta.errors[0] as { message?: string } | undefined
                return (
                  <div className="space-y-1.5">
                    <Label>Notas</Label>
                    <Textarea
                      id={field.name}
                      value={typeof field.state.value === "string" ? field.state.value : ""}
                      onChange={(e) => field.handleChange(e.target.value)}
                      onBlur={field.handleBlur}
                      aria-invalid={error?.message ? true : undefined}
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )
              }}
            </planForm.Field>
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  setPlanning(false)
                  planForm.reset(PLAN_DEFAULTS)
                }}
              >
                Cancelar
              </Button>
              <Button type="submit" disabled={plan.isPending || planForm.state.isSubmitting}>
                {plan.isPending || planForm.state.isSubmitting ? "…" : "Planear"}
              </Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>
    </div>
  )
}

/**
 * Row for a single planned transaction on the Por pagar page. Overdue rows
 * render the destructive left bar, "Vencido" badge, and destructive due-date
 * color; upcoming rows render muted styling with no badge. Both variants share
 * the Confirmar / Omitir controls.
 */
function ToPayRow({
  item,
  isOverdueRow,
  onConfirm,
  onSkip,
  skipPending,
}: {
  item: Transaction
  isOverdueRow: boolean
  onConfirm: () => void
  onSkip: () => void
  skipPending: boolean
}) {
  return (
    <li className="flex items-center justify-between gap-4 py-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <p className="truncate text-sm font-medium">{item.payee || "—"}</p>
          {isOverdueRow && <Badge variant="destructive">Vencido</Badge>}
        </div>
        <time
          dateTime={item.date}
          className="text-xs"
          style={{ color: isOverdueRow ? "var(--destructive)" : "var(--muted-foreground)" }}
        >
          {formatDate(item.date)}
        </time>
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <MoneyAmount cents={item.amount} currency={item.currency} className="text-sm font-medium" />
        <Button size="sm" variant="outline" onClick={onConfirm}>
          Confirmar
        </Button>
        <Button size="sm" variant="ghost" disabled={skipPending} onClick={onSkip}>
          Omitir
        </Button>
      </div>
    </li>
  )
}
