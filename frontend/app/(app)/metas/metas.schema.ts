import { z } from "zod"
import { positiveCents, requiredString, yearMonth } from "@/lib/schemas/primitives"

/** A new meta: a name, an amount, and the month it is wanted by (AC-1). */
export const createMetaSchema = z.object({
  name: requiredString,
  amount: positiveCents,
  targetMonth: yearMonth,
})

export type CreateMetaValues = z.infer<typeof createMetaSchema>

/** A new amount for a meta already running (AC-11). */
export const metaAmountSchema = z.object({ amount: positiveCents })

export type MetaAmountValues = z.infer<typeof metaAmountSchema>

/** A new month for a meta already running (AC-11). */
export const metaMonthSchema = z.object({ targetMonth: yearMonth })

export type MetaMonthValues = z.infer<typeof metaMonthSchema>

/** Money the owner sets aside by hand, on top of the instalment (AC-34). */
export const metaContributionSchema = z.object({ amount: positiveCents })

export type MetaContributionValues = z.infer<typeof metaContributionSchema>
