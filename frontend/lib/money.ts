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

/**
 * The whole pesos each part shows, adjusted so they add up to the whole the
 * total shows.
 *
 * Rounding every part on its own is individually right and jointly wrong: two
 * shares of 333.333,34 each read as 333.333 while their total of 666.666,68
 * reads as 666.667, leaving a peso nobody can point at. The parts with the
 * largest centavos take the difference, which is how a bill is split.
 *
 * `parts` must add up to `total` in cents; that is what the caller is showing.
 */
export function sharesAddingTo(parts: number[], total: number): number[] {
  const whole = Math.round(total / 100)
  const shown = parts.map((cents) => Math.floor(cents / 100))
  const byCentavos = parts
    .map((cents, index) => ({ index, centavos: cents % 100 }))
    .sort((a, b) => b.centavos - a.centavos)
  let left = whole - shown.reduce((sum, pesos) => sum + pesos, 0)
  for (const { index } of byCentavos) {
    if (left <= 0) break
    shown[index] += 1
    left -= 1
  }
  return shown.map((pesos) => pesos * 100)
}

function wholePesos(cents: number): number {
  return Math.round(cents / 100) * 100
}

/**
 * The same amount of money, restated in another currency at the app's single
 * rate (ADR-0031). Returns null when the rate is unknown or unusable, so a
 * caller shows nothing rather than a figure it invented.
 *
 * A peso result is whole pesos, the only peso figure the app can hold: it reads
 * one back as whole pesos and shows it as whole pesos, so the figure the owner
 * is offered is the figure that reaches his balance (AC-13). A dollar result
 * keeps its cents, which the app holds exactly (AC-4).
 *
 * What a correction offers when the owner picks an account in another currency
 * — always as a suggestion he can replace, never applied on his behalf
 * (ADR-0051). One helper for both screens: confirming a payment and moving a
 * transfer's side behave identically on purpose.
 */
export function convertCents(
  cents: number,
  from: string,
  to: string,
  usdCop: number | null,
): number | null {
  if (from === to) return cents
  if (usdCop === null || !Number.isFinite(usdCop) || usdCop <= 0) return null
  if (from === "USD" && to === "COP") return wholePesos(cents * usdCop)
  if (from === "COP" && to === "USD") return Math.round(cents / usdCop)
  return null
}

/** A figure stated for a movement, and the currency it was stated in. */
export type StatedAmount = { cents: number | null; currency: string }

/**
 * The figure to offer after the owner picks another account: the money he stated
 * restated in that account's currency, handed back untouched when he stated it
 * in that very currency, and null when there is nothing to restate or no usable
 * rate.
 *
 * A figure is always restated from the currency it was stated in, never from the
 * one on screen, so a trip out to another currency and back offers the figure
 * the movement already held rather than one the owner never wrote (AC-21).
 *
 * One helper for both screens that offer an account: correcting a movement and
 * confirming a payment behave identically on purpose (ADR-0051).
 */
export function amountForAccount(
  stated: StatedAmount,
  to: string,
  usdCop: number | null,
): number | null {
  if (stated.cents === null) return null
  return convertCents(stated.cents, stated.currency, to, usdCop)
}

/**
 * The currency an account holds, or null while the accounts have not arrived.
 *
 * The null is what lets a screen fall back to the currency the movement it is
 * showing already carries, rather than to pesos: a dollar figure read before the
 * list of accounts must not be restated as pesos on the strength of a list
 * nobody has seen yet. One helper for the three screens that offer an account —
 * correcting a movement, confirming a payment and moving a repeating charge
 * behave identically on purpose (ADR-0051).
 */
export function currencyHeldBy(
  accounts: { id: number; currency: string }[] | undefined,
  id: number | null,
): string | null {
  return accounts?.find((a) => a.id === id)?.currency ?? null
}

/**
 * The currency an account holds, or pesos when the account is not known yet.
 *
 * For a screen that has nothing else to fall back on — a blank form, where no
 * movement is on hand to keep the figure honest until the accounts arrive.
 */
export function currencyOf(
  accounts: { id: number; currency: string }[] | undefined,
  id: number | null,
): string {
  return currencyHeldBy(accounts, id) ?? "COP"
}
