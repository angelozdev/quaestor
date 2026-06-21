/**
 * Format an integer amount of cents for display (es-CO).
 * Amounts arrive as positive integer cents (SCALE=100 for both COP and USD).
 * COP: "$ 1.234.567" (no decimals). USD: "US$ 12.34" (2 decimals).
 * This is display-only; the client never does business arithmetic on amounts.
 */
export function formatCents(cents: number, currency: string): string {
  if (currency === "USD") {
    const major = cents / 100
    const formatted = new Intl.NumberFormat("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(major)
    return `US$ ${formatted}`
  }
  const pesos = Math.round(cents / 100)
  const formatted = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(pesos)
  return `$ ${formatted}`
}
