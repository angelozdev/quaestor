"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { endOfMonth, endOfWeek, format, startOfMonth, startOfWeek } from "date-fns"
import { useState } from "react"
import { toast } from "sonner"
import { EmptyState } from "@/components/empty-state"
import { EntitySelect } from "@/components/entity-select"
import { ErrorState } from "@/components/error-state"
import { FormField } from "@/components/form-field"
import { MoneyAmount } from "@/components/money-amount"
import { MoneyInput } from "@/components/money-input"
import { PageHeader } from "@/components/page-header"
import { listAccounts } from "@/lib/api/accounts"
import { listCategories } from "@/lib/api/categories"
import { confirmPayment, planPayment, skipPlanned, toPay } from "@/lib/api/planned"
import { type Account, ApiError, applyApiErrorsToForm, type Transaction } from "@/lib/api/types"
import { formatDate } from "@/lib/date"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Badge, Button, Dialog, DialogPopup, DialogTitle, Input, Label, Textarea } from "@/ui"
import { type PlanPaymentValues, planPaymentSchema } from "./to-pay.schema"

type Scope = "week" | "month"

function currencyOf(accounts: Account[] | undefined, id: number | null): string {
  return accounts?.find((a) => a.id === id)?.currency ?? "COP"
}

function windowFor(scope: Scope) {
  const now = new Date()
  const [since, until] =
    scope === "week"
      ? [startOfWeek(now, { weekStartsOn: 1 }), endOfWeek(now, { weekStartsOn: 1 })]
      : [startOfMonth(now), endOfMonth(now)]
  return { since: format(since, "yyyy-MM-dd"), until: format(until, "yyyy-MM-dd") }
}

const PLAN_DEFAULTS: PlanPaymentValues = {
  payee: "",
  accountId: null,
  amount: Number.NaN,
  dueDate: "",
  categoryId: null,
  notes: undefined,
}

export default function ToPayPage() {
  const qc = useQueryClient()
  const [scope, setScope] = useState<Scope>("week")
  const { since, until } = windowFor(scope)

  const [confirming, setConfirming] = useState<Transaction | null>(null)
  const [cAmount, setCAmount] = useState<number | null>(null)
  const [cDate, setCDate] = useState("")

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

  const planAccountId = planForm.state.values.accountId
  const planCurrency = currencyOf(accounts.data, planAccountId)

  const onErr = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Error")
  const done = (msg: string) => {
    toast.success(msg)
    invalidate(qc, "plannedWrite")
  }

  const confirm = useMutation({
    mutationFn: () => {
      if (!confirming) throw new Error("confirming transaction is required")
      return confirmPayment(confirming.id, {
        amount: cAmount ?? undefined,
        date: cDate || undefined,
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
        category_id: values.categoryId,
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
    setCAmount(item.amount)
    setCDate(item.date)
  }

  return (
    <div className="space-y-6">
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
      />

      <div
        className="inline-flex items-center gap-1 rounded-md p-0.5"
        style={{ background: "var(--muted)" }}
      >
        {(["week", "month"] as Scope[]).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setScope(s)}
            className="rounded px-2.5 py-1 text-xs transition-all"
            style={{
              background: scope === s ? "var(--card)" : "transparent",
              color: scope === s ? "var(--foreground)" : "var(--muted-foreground)",
              fontWeight: scope === s ? 500 : 400,
            }}
          >
            {s === "week" ? "Esta semana" : "Este mes"}
          </button>
        ))}
      </div>

      {list.isError && (
        <ErrorState message="No se pudo cargar lo pendiente" onRetry={() => list.refetch()} />
      )}

      {list.data && (
        <>
          <p className="text-3xl font-bold tabular-nums tracking-tight">
            {formatCents(list.data.total_base, "COP")}
          </p>
          {list.data.overdue.length === 0 && list.data.upcoming.length === 0 ? (
            <EmptyState message="Nada pendiente en este periodo." />
          ) : (
            <div className="space-y-4">
              {list.data.overdue.length > 0 && (
                <section className="space-y-0">
                  <header className="flex items-center gap-2 pb-2">
                    <p
                      className="text-xs font-medium uppercase tracking-wider"
                      style={{ color: "var(--muted-foreground)" }}
                    >
                      Vencidos
                    </p>
                    <Badge variant="destructive">{list.data.overdue.length}</Badge>
                  </header>
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
                </section>
              )}

              {list.data.upcoming.length > 0 && (
                <section className="space-y-0">
                  <header className="pb-2">
                    <h2
                      className="text-xs font-medium uppercase tracking-wider"
                      style={{ color: "var(--muted-foreground)" }}
                    >
                      {scope === "week" ? "Esta semana" : "Este mes"}
                    </h2>
                  </header>
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
                </section>
              )}
            </div>
          )}
        </>
      )}

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
                <Label>Monto real ({confirming.currency})</Label>
                <MoneyInput currency={confirming.currency} value={cAmount} onChange={setCAmount} />
              </div>
              <div className="space-y-1.5">
                <Label>Fecha</Label>
                <Input type="date" value={cDate} onChange={(e) => setCDate(e.target.value)} />
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
                  <div className="space-y-1.5">
                    <Label>Categoría</Label>
                    <EntitySelect
                      value={field.state.value as number | null}
                      onChange={(v) => field.handleChange(v as never)}
                      queryKey={qk.categories(false)}
                      queryFn={() => listCategories(false)}
                      allowNullLabel="Sin categoría"
                    />
                    {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
                  </div>
                )
              }}
            </planForm.Field>
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
    <li className="relative flex items-center justify-between gap-4 py-3 pl-3">
      {isOverdueRow && (
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 w-[2px] rounded-full"
          style={{ background: "var(--destructive)" }}
        />
      )}
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
        <MoneyAmount
          cents={item.amount}
          currency={item.currency}
          className="text-sm font-medium"
        />
        <Button size="sm" onClick={onConfirm}>
          Confirmar
        </Button>
        <Button size="sm" variant="ghost" disabled={skipPending} onClick={onSkip}>
          Omitir
        </Button>
      </div>
    </li>
  )
}
