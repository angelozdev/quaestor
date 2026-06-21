import type { TxType } from "@/lib/api/types"
import { formatCents } from "@/lib/money"

export function MoneyAmount({
  cents,
  currency,
  type,
  className = "",
}: {
  cents: number
  currency: string
  type?: TxType
  className?: string
}) {
  const color =
    type === "expense"
      ? "var(--expense)"
      : type === "income"
        ? "var(--income)"
        : "var(--foreground)"

  return (
    <span className={`tabular-nums ${className}`} style={{ color }}>
      {formatCents(cents, currency)}
    </span>
  )
}
