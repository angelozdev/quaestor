import { z } from "zod"
import { messages, minNumberMessage } from "@/lib/schemas/messages"
import { positiveCents } from "@/lib/schemas/primitives"

const yearMonth = z.string().regex(/^\d{4}-\d{2}$/, messages.mesInvalido)

/**
 * The form's own check: a rule needs the parameter that rule is made of.
 * The refusal itself lives in the service — this only saves the round trip.
 */
export const createFundSchema = z
  .object({
    categoryId: z.number({ error: messages.required }).int().positive(messages.required).nullable(),
    rule: z.enum(["fixed", "average", "from-recurring", "target-by-date"]),
    startMonth: yearMonth,
    accumulates: z.boolean(),
    amount: positiveCents.nullable(),
    windowMonths: z.number().int().min(1, minNumberMessage(1)).nullable(),
    targetAmount: positiveCents.nullable(),
    targetMonth: z.union([yearMonth, z.literal("")]),
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
    if (value.rule === "target-by-date") {
      if (value.targetAmount === null) {
        ctx.addIssue({ code: "custom", message: messages.required, path: ["targetAmount"] })
      }
      if (value.targetMonth === "") {
        ctx.addIssue({ code: "custom", message: messages.required, path: ["targetMonth"] })
      }
    }
  })

export type CreateFundValues = z.infer<typeof createFundSchema>
