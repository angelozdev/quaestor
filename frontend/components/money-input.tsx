"use client"

import { NumericFormat } from "react-number-format"
import { decimalSeparatorFor, thousandsSeparatorFor } from "@/lib/money"
import { Input } from "@/ui"

export function MoneyInput({
  currency,
  value,
  onChange,
  id,
  placeholder,
  disabled,
}: {
  currency: string
  value: number | null
  onChange: (cents: number | null) => void
  id?: string
  placeholder?: string
  disabled?: boolean
}) {
  const prefix = currency === "USD" ? "US$" : "$"

  return (
    <div className="flex items-center gap-2">
      <span className="text-sm text-muted-foreground tabular-nums">{prefix}</span>
      <NumericFormat
        customInput={Input}
        id={id}
        inputMode={currency === "USD" ? "decimal" : "numeric"}
        placeholder={placeholder}
        disabled={disabled}
        className="tabular-nums"
        value={value === null ? "" : value / 100}
        thousandSeparator={thousandsSeparatorFor(currency)}
        decimalSeparator={decimalSeparatorFor(currency)}
        decimalScale={currency === "USD" ? 2 : 0}
        fixedDecimalScale={false}
        allowNegative={false}
        onValueChange={(values, sourceInfo) => {
          if (sourceInfo.source !== "event") return
          onChange(values.floatValue === undefined ? null : Math.round(values.floatValue * 100))
        }}
      />
    </div>
  )
}
