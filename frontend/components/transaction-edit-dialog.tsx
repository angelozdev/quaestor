"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { toast } from "sonner"
import { EntitySelect } from "@/components/entity-select"
import { FormField } from "@/components/form-field"
import { MetaField } from "@/components/meta-field"
import { MoneyInput } from "@/components/money-input"
import { TagChipsInput } from "@/components/tag-chips-input"
import {
  type TransactionEditValues,
  txEditSchema,
} from "@/components/transaction-edit-dialog.schema"
import { listAccounts } from "@/lib/api/accounts"
import { listCategories } from "@/lib/api/categories"
import { getFx } from "@/lib/api/fx"
import { correctTransaction, listTransactions, updateTransaction } from "@/lib/api/transactions"
import {
  ApiError,
  applyApiErrorsToForm,
  type CorrectionBody,
  type Transaction,
} from "@/lib/api/types"
import { yearMonthOf } from "@/lib/date"
import {
  amountForAccount,
  currencyHeldBy,
  currencyOf,
  formatCents,
  type StatedAmount,
} from "@/lib/money"
import { invalidate, qk } from "@/lib/query"
import { findCounterpart } from "@/lib/transfers"
import { useStatedAmount } from "@/lib/use-stated-amount"
import { useTagNames } from "@/lib/use-tag-names"
import { Badge, Button, Dialog, DialogPopup, DialogTitle, Label } from "@/ui"

function valuesFromTx(tx: Transaction): TransactionEditValues {
  return {
    payee: tx.payee ?? "",
    categoryId: tx.category_id,
    date: tx.date,
    notes: tx.notes ?? "",
    tags: tx.tags,
    metaId: tx.meta_id,
  }
}

/** The other leg of the transfer this movement belongs to, once it has arrived. */
function useCounterpart(tx: Transaction): Transaction | undefined {
  const groupFilter = { transfer_group_id: tx.transfer_group_id ?? undefined }
  const siblings = useQuery({
    queryKey: qk.transactions(groupFilter),
    queryFn: () => listTransactions(groupFilter),
    enabled: tx.transfer_group_id !== null,
  })
  return findCounterpart(siblings.data, tx)
}

/**
 * A correction states only what the owner changed, so an untouched field is
 * never restated: the account when it moved, the amount when it was rewritten,
 * and a transfer's two figures together — the only route to what a transfer
 * moved, since a side is never restated on its own (AC-11, AC-12, ADR-0051).
 *
 * `missing` is what the correction has still not been told, so nothing at all is
 * written. `refusal` is a fully stated correction that cannot be made in one
 * save: the balance-safe edit beside it was never at risk and is still saved,
 * and the owner is told the money stayed as it was rather than left to believe
 * a figure he wrote was applied (AC-23).
 */
function statedCorrection({
  tx,
  counterpart,
  accountId,
  currency,
  amount,
  counterpartAmount,
}: {
  tx: Transaction
  counterpart: Transaction | undefined
  accountId: number | null
  currency: string
  amount: number | null
  counterpartAmount: number | null
}) {
  const isTransfer = tx.type === "transfer"
  const moved = accountId !== tx.account_id
  const ridesWithTheMove = isTransfer && currency !== tx.currency
  const pair = tx.transfer_group_id !== null ? counterpart : undefined
  const restatingThePair = isTransfer && !moved && pair !== undefined
  const otherSide = restatingThePair && pair.currency !== tx.currency ? pair : null
  const amountIsAsked = !isTransfer || ridesWithTheMove || pair !== undefined
  const amountRestated = amount !== tx.amount
  const counterpartRestated =
    pair !== undefined && pair.currency !== tx.currency && counterpartAmount !== pair.amount
  const halvesWouldDiverge =
    pair !== undefined && pair.currency === currency && amount !== pair.amount
  const unstated = { otherSide, amountIsAsked, body: null }
  const missing = (message: string) => ({ ...unstated, missing: message, refusal: null })
  const refuse = (message: string) => ({ ...unstated, missing: null, refusal: message })

  if (accountId === null) return missing("Elige la cuenta del movimiento.")
  if (amountIsAsked && amount === null) return missing("Escribe el monto del movimiento.")
  if (otherSide !== null && counterpartAmount === null)
    return missing("Escribe los dos montos de la transferencia.")
  if (isTransfer && moved && (counterpartRestated || halvesWouldDiverge))
    return refuse("Mueve la transferencia de cuenta o corrige su monto, de a uno.")

  const other = otherSide === null ? amount : counterpartAmount
  const figuresRestated = amountRestated || counterpartRestated
  const body: CorrectionBody = {}
  if (moved) body.account_id = accountId
  if (restatingThePair && figuresRestated && amount !== null && other !== null) {
    body.sent = tx.transfer_direction === "out" ? amount : other
    body.received = tx.transfer_direction === "out" ? other : amount
  } else if (amountIsAsked && amountRestated && amount !== null) {
    body.amount = amount
  }
  return {
    otherSide,
    amountIsAsked,
    missing: null,
    refusal: null,
    body: Object.keys(body).length > 0 ? body : null,
  }
}

/**
 * The figure to offer once another account is chosen. The figure the owner
 * stated comes back untouched in the currency he stated it in. A transfer's leg
 * landing in the currency its other half already holds is offered that half's
 * own figure, because two halves in one currency carry the same amount (AC-11);
 * every other move is offered the same money restated at the app's rate
 * (AC-13).
 */
function amountForChosenAccount({
  stated,
  to,
  usdCop,
  counterpart,
}: {
  stated: StatedAmount
  to: string
  usdCop: number | null
  counterpart: Transaction | undefined
}): number | null {
  if (stated.currency === to) return stated.cents
  if (counterpart !== undefined && counterpart.currency === to) return counterpart.amount
  return amountForAccount(stated, to, usdCop)
}

/** A correction that did not happen, after the balance-safe edit was saved. */
class CorrectionRefused extends Error {
  constructor(
    message: string,
    readonly cause?: unknown,
  ) {
    super(message)
  }
}

function TransferPairInfo({ tx, counterpart }: { tx: Transaction; counterpart?: Transaction }) {
  const accounts = useQuery({
    queryKey: qk.accounts(true),
    queryFn: () => listAccounts(true),
  })
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

/**
 * The merchant's price behind a charge, when the account was debited in another
 * currency.
 *
 * The figure is read from the rule the charge came from, so it stays the price
 * that was really charged however the rate moves afterwards — a July charge of
 * US$32,10 keeps reading 99.900 COP in December (AC-21). A movement that came
 * from no rule, or from one that agrees with its account, has nothing extra to
 * say and says nothing.
 */
function RulePriceNote({ tx }: { tx: Transaction }) {
  if (tx.rule_amount === null || tx.rule_currency === null) return null
  return <p>Precio de la regla: {formatCents(tx.rule_amount, tx.rule_currency)}</p>
}

function EditTransactionForm({ tx, onDone }: { tx: Transaction; onDone: () => void }) {
  const qc = useQueryClient()
  const tagSuggestions = useTagNames()
  const isTransfer = tx.type === "transfer"
  const isIncome = tx.type === "income"
  const monthOfPurchase = tx.type === "expense" ? yearMonthOf(tx.date) : null
  const [accountId, setAccountId] = useState<number | null>(tx.account_id)
  const money = useStatedAmount({ cents: tx.amount, currency: tx.currency })
  const [statedOther, setStatedOther] = useState<number | null | undefined>(undefined)
  const accountsQuery = useQuery({
    queryKey: qk.accounts(false),
    queryFn: () => listAccounts(false),
  })
  const fx = useQuery({ queryKey: qk.fx(), queryFn: getFx })
  const usdCop = fx.data ? Number(fx.data.usd_cop) : null
  const counterpart = useCounterpart(tx)
  const counterpartAmount = statedOther === undefined ? (counterpart?.amount ?? null) : statedOther
  const currency = currencyHeldBy(accountsQuery.data, accountId) ?? tx.currency
  const { otherSide, amountIsAsked, missing, refusal, body } = statedCorrection({
    tx,
    counterpart,
    accountId,
    currency,
    amount: money.amount,
    counterpartAmount,
  })
  const sending = tx.transfer_direction === "out"

  const form = useTanStackForm({
    defaultValues: valuesFromTx(tx),
    validators: { onChange: txEditSchema(isTransfer) },
    onSubmit: async ({ value }) => {
      if (missing !== null) {
        toast.error(missing)
        return
      }
      update.mutate(value)
    },
  })

  const update = useMutation({
    mutationFn: async (values: TransactionEditValues) => {
      const edited = await updateTransaction(tx.id, {
        payee: values.payee && values.payee.length > 0 ? values.payee : undefined,
        date: values.date,
        category_id: values.categoryId,
        notes: values.notes && values.notes.length > 0 ? values.notes : null,
        tags: values.tags,
        meta_id: values.metaId,
      })
      if (refusal !== null) throw new CorrectionRefused(refusal)
      if (body === null) return edited
      try {
        return await correctTransaction(tx.id, body)
      } catch (e: unknown) {
        throw new CorrectionRefused(e instanceof ApiError ? e.message : "Error", e)
      }
    },
    onSuccess: () => {
      toast.success("Transacción actualizada")
      onDone()
    },
    onError: (e: unknown) => {
      const cause = e instanceof CorrectionRefused ? e.cause : e
      applyApiErrorsToForm(form, cause)
      toast.error(
        e instanceof CorrectionRefused
          ? `Se guardaron los datos, pero el monto y la cuenta quedaron como estaban: ${e.message}`
          : cause instanceof ApiError
            ? cause.message
            : "Error",
      )
    },
    onSettled: () => invalidate(qc, "transactionWrite"),
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
        {tx.transfer_group_id && <TransferPairInfo tx={tx} counterpart={counterpart} />}
        <p>
          {tx.type}
          {!amountIsAsked && ` · ${formatCents(tx.amount, tx.currency)}`}
        </p>
        <RulePriceNote tx={tx} />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="tx-edit-account">Cuenta</Label>
        <EntitySelect
          id="tx-edit-account"
          value={accountId}
          onChange={(chosen) => {
            const next = chosen as number | null
            const to = currencyOf(accountsQuery.data, next)
            setAccountId(next)
            if (to !== currency) {
              money.offer(amountForChosenAccount({ stated: money.stated, to, usdCop, counterpart }))
            }
          }}
          queryKey={qk.accounts(false)}
          queryFn={() => listAccounts(false)}
        />
      </div>
      {amountIsAsked && (
        <div className="space-y-1.5">
          <Label htmlFor="tx-edit-amount">
            {otherSide === null
              ? `Monto (${currency})`
              : sending
                ? `Monto enviado (${currency})`
                : `Monto recibido (${currency})`}
          </Label>
          <MoneyInput
            id="tx-edit-amount"
            currency={currency}
            value={money.amount}
            onChange={(cents) => money.write(cents, currency)}
          />
        </div>
      )}
      {otherSide !== null && (
        <div className="space-y-1.5">
          <Label htmlFor="tx-edit-counterpart-amount">
            {sending
              ? `Monto recibido (${otherSide.currency})`
              : `Monto enviado (${otherSide.currency})`}
          </Label>
          <MoneyInput
            id="tx-edit-counterpart-amount"
            currency={otherSide.currency}
            value={counterpartAmount}
            onChange={setStatedOther}
          />
        </div>
      )}
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
      {monthOfPurchase !== null && (
        <form.Field name="metaId">
          {(field) => (
            <MetaField
              id="tx-edit-meta"
              month={monthOfPurchase}
              value={field.state.value as number | null}
              onChange={(chosen) => field.handleChange(chosen as never)}
            />
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
