/**
 * Implied transfer rate (received ÷ sent) for cross-currency transfers.
 * Information only (AC-8): shown live in the form, never sent to the API.
 * Returns null unless both amounts are positive finite cents.
 */
export function impliedRate(sentCents: number | null, receivedCents: number | null): number | null {
  if (sentCents === null || receivedCents === null) return null
  if (!Number.isFinite(sentCents) || !Number.isFinite(receivedCents)) return null
  if (sentCents <= 0 || receivedCents <= 0) return null
  return receivedCents / sentCents
}

export function formatRate(rate: number): string {
  return new Intl.NumberFormat("es-CO", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(rate)
}

/** Narrow an unknown form value to finite number cents, else null. */
export function finiteOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null
}

/**
 * Format an integer amount of cents for display (es-CO).
 * Amounts arrive as positive integer cents (100 cents per major unit for both COP and USD).
 * COP: "$ 1.234.567" (no decimals). USD: "US$ 12.34" (2 decimals).
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
