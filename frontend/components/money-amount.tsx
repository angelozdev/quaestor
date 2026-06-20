import { formatCents } from "@/lib/money";
import type { TxType } from "@/lib/api";

export function MoneyAmount({
  cents,
  currency,
  type,
  className = "",
}: {
  cents: number;
  currency: string;
  type?: TxType;
  className?: string;
}) {
  const sign = type === "expense" ? "−" : type === "income" ? "+" : "";
  const color =
    type === "expense" ? "text-red-600" : type === "income" ? "text-green-600" : "";
  return (
    <span className={`tabular-nums ${color} ${className}`}>
      {sign}
      {formatCents(cents, currency)}
    </span>
  );
}
