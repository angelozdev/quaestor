import { z } from "zod"
import { messages } from "@/lib/schemas/messages"
import { positiveCents, requiredString } from "@/lib/schemas/primitives"

export const assignBudgetSchema = z.object({
  category: requiredString,
  amount: positiveCents,
  yearMonth: z.string().regex(/^\d{4}-\d{2}$/, messages.mesInvalido),
})

export type AssignBudgetValues = z.infer<typeof assignBudgetSchema>
