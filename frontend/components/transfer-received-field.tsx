"use client"

import { MoneyInput } from "@/components/money-input"
import { formatImpliedRate, impliedRate } from "@/lib/money"
import { Label } from "@/ui"

export function TransferReceivedField({
  active,
  sentCurrency,
  receivedCurrency,
  sentCents,
  receivedCents,
  onChange,
  errorMessage,
}: {
  active: boolean
  sentCurrency: string
  receivedCurrency: string
  sentCents: number | null
  receivedCents: number | null
  onChange: (cents: number | null) => void
  errorMessage?: string
}) {
  if (!active || sentCurrency === receivedCurrency) return null
  const rate = impliedRate(sentCents, receivedCents)
  return (
    <div className="space-y-1.5">
      <Label>Monto recibido * ({receivedCurrency})</Label>
      <MoneyInput currency={receivedCurrency} value={receivedCents} onChange={onChange} />
      {rate !== null && (
        <p className="text-xs" style={{ color: "var(--muted-foreground)" }}>
          Tasa implícita: {formatImpliedRate(rate)} (solo informativa)
        </p>
      )}
      {errorMessage && <p className="text-xs text-destructive">{errorMessage}</p>}
    </div>
  )
}
