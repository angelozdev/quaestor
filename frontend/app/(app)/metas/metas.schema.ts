import { z } from "zod"
import { positiveCents, requiredString, yearMonth } from "@/lib/schemas/primitives"

/** A new meta: a name, an amount, and the month it is wanted by (AC-1). */
export const createMetaSchema = z.object({
  name: requiredString,
  amount: positiveCents,
  targetMonth: yearMonth,
})

export type CreateMetaValues = z.infer<typeof createMetaSchema>

/** A new amount for a meta already running, and the money it is set aside with (AC-11, AC-34). */
export const metaAmountSchema = z.object({ amount: positiveCents })

/** A new month for a meta already running (AC-11). */
export const metaMonthSchema = z.object({ targetMonth: yearMonth })
