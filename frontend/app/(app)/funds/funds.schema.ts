import { z } from "zod"
import { messages, minNumberMessage } from "@/lib/schemas/messages"
import { positiveCents } from "@/lib/schemas/primitives"

const yearMonth = z.string().regex(/^\d{4}-\d{2}$/, messages.mesInvalido)

/**
 * The form's own check: a rule needs the parameter that rule is made of.
 * The refusal itself lives in the service — this only saves the round trip.
 *
 * Whether the money accumulates is not asked for and is not here: the entry
 * point the owner used decides it (product ADR-042).
 */
export const createFundSchema = z
  .object({
    categoryId: z.number({ error: messages.required }).int().positive(messages.required).nullable(),
    rule: z.enum(["fixed", "average", "from-recurring"]),
    startMonth: yearMonth,
    amount: positiveCents.nullable(),
    windowMonths: z.number().int().min(1, minNumberMessage(1)).nullable(),
  })
  .superRefine((value, ctx) => {
    if (value.categoryId === null) {
      ctx.addIssue({ code: "custom", message: messages.required, path: ["categoryId"] })
    }
    if (value.rule === "fixed" && value.amount === null) {
      ctx.addIssue({ code: "custom", message: messages.required, path: ["amount"] })
    }
    if (value.rule === "average" && value.windowMonths === null) {
      ctx.addIssue({ code: "custom", message: messages.required, path: ["windowMonths"] })
    }
  })

export type CreateFundValues = z.infer<typeof createFundSchema>
