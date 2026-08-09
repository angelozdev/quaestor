import { z } from "zod"
import { maxNumberMessage, messages, minNumberMessage } from "./messages"

/** Integer cents >= 0. Used for balances and zero-allowed amounts. */
export const nonNegativeCents = z
  .number({ error: messages.soloNumeros })
  .int(messages.soloNumerosEnteros)
  .nonnegative(minNumberMessage(0))

/** Integer cents > 0. Used for expenses, income, transfers, contributions. */
export const positiveCents = z
  .number({ error: messages.soloNumeros })
  .int(messages.soloNumerosEnteros)
  .positive(messages.debeSerPositivo)

/** Recurring interval count: integer 1..1000. */
export const intervalCount = z
  .number({ error: messages.soloNumeros })
  .int(messages.soloNumerosEnteros)
  .min(1, minNumberMessage(1))
  .max(1000, maxNumberMessage(1000))

/** USD→COP rate: float (0, 100000]. */
export const fxRate = z
  .number({ error: messages.soloNumeros })
  .positive(messages.debeSerPositivo)
  .max(100_000, maxNumberMessage(100_000))

/** Wire month YYYY-MM. Native <input type="month"> produces this. */
export const yearMonth = z.string().regex(/^\d{4}-\d{2}$/, messages.mesInvalido)

/** ISO date string YYYY-MM-DD. Native <input type="date"> produces this. */
export const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, messages.fechaInvalida)

/** Required, trimmed, non-empty string with sane length. */
export const requiredString = z.string().trim().min(1, messages.required).max(120, messages.max120)

/** Optional free-form string, trimmed, capped. */
export const optionalString = z.string().trim().max(500, messages.max500).optional()

/** A movement says what it was for: an existing category, or a name to create.
 *
 * Exactly one of the two — mandatory since feature 008 (ADR-0042). Apply with
 * `.superRefine(categoryChosen)` on any form that records money.
 */
export const categoryChosen = (
  value: { categoryId: number | null; newCategory?: string },
  ctx: z.RefinementCtx,
): void => {
  const named = (value.newCategory ?? "").trim().length > 0
  if (value.categoryId === null && !named) {
    ctx.addIssue({ code: "custom", message: messages.required, path: ["categoryId"] })
  }
  if (value.categoryId !== null && named) {
    ctx.addIssue({ code: "custom", message: messages.categoriaAmbigua, path: ["categoryId"] })
  }
}
