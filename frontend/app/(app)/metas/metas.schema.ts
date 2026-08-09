import { z } from "zod"
import {
  nonNegativeCents,
  positiveCents,
  requiredString,
  yearMonth,
} from "@/lib/schemas/primitives"

/** The currencies a meta may be held in (AC-26). */
export const META_CURRENCIES = ["COP", "USD"] as const

/**
 * A new meta: a name, an amount, the month it is wanted by (AC-1), the currency
 * it is held in (AC-26) and what the owner had already put by (AC-34).
 *
 * What is stated as already saved costs no month — it is money set aside before
 * the meta existed, which is what `Aportar` cannot do.
 */
export const createMetaSchema = z.object({
  name: requiredString,
  amount: positiveCents,
  targetMonth: yearMonth,
  currency: z.enum(META_CURRENCIES),
  statedOpening: nonNegativeCents.optional(),
})

export type CreateMetaValues = z.infer<typeof createMetaSchema>

/** A new amount for a meta already running, and the money it is set aside with (AC-11, AC-34). */
export const metaAmountSchema = z.object({ amount: positiveCents })

/**
 * One free-text answer a running meta asks for — a new name, or a new month.
 *
 * Both are one field under one label, so they are one schema shape and one
 * component (AC-11); only the rule that judges the text differs.
 */
const asked = (rule: z.ZodType<string, string>) => z.object({ value: rule })

export type AskedText = ReturnType<typeof asked>

export const metaMonthSchema = asked(yearMonth)
export const metaNameSchema = asked(requiredString)
