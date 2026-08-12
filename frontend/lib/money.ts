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
 * The null is what lets a screen fall back to the figure it is already holding
 * rather than to pesos: a dollar payment read before the list of accounts must
 * not be offered in pesos on the strength of a list nobody has seen yet.
 */
export function currencyHeldBy(
  accounts: { id: number; currency: string }[] | undefined,
  id: number | null,
): string | null {
  return accounts?.find((a) => a.id === id)?.currency ?? null
}

/** The currency an account holds, or pesos when the account is not known yet. */
export function currencyOf(
  accounts: { id: number; currency: string }[] | undefined,
  id: number | null,
): string {
  return accounts?.find((a) => a.id === id)?.currency ?? "COP"
}

/**
 * The currency a movement is stated in while its account is being chosen: its
 * own until it moves, and the chosen account's from then on.
 *
 * A movement carries its currency the moment it is read, so a list of accounts
 * that has not arrived yet never restates a dollar figure as pesos. One helper
 * for both screens that offer an account: correcting a movement and confirming
 * a payment behave identically on purpose (ADR-0051).
 */
export function currencyForAccount(
  movement: { account_id: number; currency: string } | null,
  accounts: { id: number; currency: string }[] | undefined,
  chosen: number | null,
): string {
  if (movement !== null && chosen === movement.account_id) return movement.currency
  return currencyOf(accounts, chosen)
}
