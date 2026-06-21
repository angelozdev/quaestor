"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { endOfMonth, endOfWeek, format, startOfMonth, startOfWeek } from "date-fns"
import { useState } from "react"
import { toast } from "sonner"
import { EmptyState } from "@/components/empty-state"
import { EntitySelect } from "@/components/entity-select"
import { ErrorState } from "@/components/error-state"
import { MoneyAmount } from "@/components/money-amount"
import { MoneyInput } from "@/components/money-input"
import { PageHeader } from "@/components/page-header"
import { listAccounts } from "@/lib/api/accounts"
import { listCategories } from "@/lib/api/categories"
import { confirmPayment, planPayment, skipPlanned, toPay } from "@/lib/api/planned"
import { type Account, ApiError, type Transaction } from "@/lib/api/types"
import { formatCents } from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { Button, Dialog, DialogPopup, DialogTitle, Input, Label, Textarea } from "@/ui"

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

export default function ToPayPage() {
  const qc = useQueryClient()
  const [scope, setScope] = useState<Scope>("week")
  const { since, until } = windowFor(scope)

  const [confirming, setConfirming] = useState<Transaction | null>(null)
  const [cAmount, setCAmount] = useState<number | null>(null)
  const [cDate, setCDate] = useState("")

  const [planning, setPlanning] = useState(false)
  const [pPayee, setPPayee] = useState("")
  const [pAmount, setPAmount] = useState<number | null>(null)
  const [pDue, setPDue] = useState("")
  const [pAccount, setPAccount] = useState<number | null>(null)
  const [pCategory, setPCategory] = useState<number | null>(null)
  const [pNotes, setPNotes] = useState("")

  const list = useQuery({ queryKey: qk.toPay(since, until), queryFn: () => toPay(since, until) })
  const accounts = useQuery({ queryKey: qk.accounts(false), queryFn: () => listAccounts(false) })

  const planCurrency = currencyOf(accounts.data, pAccount)

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
    mutationFn: () => {
      if (pAmount === null || pAccount === null) {
        throw new Error("amount and account are required to plan a payment")
      }
      return planPayment({
        payee: pPayee,
        amount: pAmount,
        due_date: pDue,
        account_id: pAccount,
        category_id: pCategory,
        notes: pNotes || undefined,
      })
    },
    onSuccess: () => {
      done("Pago planeado")
      setPlanning(false)
      setPPayee("")
      setPAmount(null)
      setPDue("")
      setPAccount(null)
      setPCategory(null)
      setPNotes("")
    },
    onError: onErr,
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
        action={<Button onClick={() => setPlanning(true)}>Planear pago</Button>}
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
          {list.data.items.length === 0 ? (
            <EmptyState message="Nada pendiente en este periodo." />
          ) : (
            <ul className="divide-y" style={{ borderColor: "var(--border)" }}>
              {list.data.items.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-4 py-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.payee || "—"}</p>
                    <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
                      {item.date}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <MoneyAmount
                      cents={item.amount}
                      currency={item.currency}
                      className="text-sm font-medium"
                    />
                    <Button size="sm" onClick={() => openConfirm(item)}>
                      Confirmar
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={skip.isPending}
                      onClick={() => skip.mutate(item.id)}
                    >
                      Omitir
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
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
      <Dialog open={planning} onOpenChange={setPlanning}>
        <DialogPopup>
          <DialogTitle>Planear pago</DialogTitle>
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (pPayee && pAmount !== null && pDue && pAccount !== null) plan.mutate()
            }}
            className="space-y-4"
          >
            <div className="space-y-1.5">
              <Label>Beneficiario *</Label>
              <Input value={pPayee} onChange={(e) => setPPayee(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Cuenta *</Label>
              <EntitySelect
                value={pAccount}
                onChange={setPAccount}
                queryKey={qk.accounts(false)}
                queryFn={() => listAccounts(false)}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Monto * ({planCurrency})</Label>
              <MoneyInput currency={planCurrency} value={pAmount} onChange={setPAmount} />
            </div>
            <div className="space-y-1.5">
              <Label>Fecha de vencimiento *</Label>
              <Input type="date" value={pDue} onChange={(e) => setPDue(e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Categoría</Label>
              <EntitySelect
                value={pCategory}
                onChange={setPCategory}
                queryKey={qk.categories(false)}
                queryFn={() => listCategories(false)}
                allowNullLabel="Sin categoría"
              />
            </div>
            <div className="space-y-1.5">
              <Label>Notas</Label>
              <Textarea value={pNotes} onChange={(e) => setPNotes(e.target.value)} />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" onClick={() => setPlanning(false)}>
                Cancelar
              </Button>
              <Button
                type="submit"
                disabled={
                  plan.isPending || !pPayee || pAmount === null || !pDue || pAccount === null
                }
              >
                {plan.isPending ? "…" : "Planear"}
              </Button>
            </div>
          </form>
        </DialogPopup>
      </Dialog>
    </div>
  )
}
