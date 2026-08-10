import type { TxType } from "@/lib/api/types"
import { formatCents } from "@/lib/money"

/**
 * An amount, with direction said only where direction is news.
 *
 * Money going out is the default case on every screen in this app, so colouring
 * it would tint almost every figure and discriminate nothing. Green marks the
 * exception — money coming in. Red is reserved for what is wrong (an overdue
 * date, a negative net) and is applied by the screen that knows it, not here.
 */
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
  return (
    <span
      className={`tabular-nums ${className}`}
      style={{ color: type === "income" ? "var(--income)" : "var(--foreground)" }}
    >
      {formatCents(cents, currency)}
    </span>
  )
}
