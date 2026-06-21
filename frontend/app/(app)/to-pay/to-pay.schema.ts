import { z } from "zod"
import { messages } from "@/lib/schemas/messages"
import { isoDate, positiveCents, requiredString } from "@/lib/schemas/primitives"

export const planPaymentSchema = z
  .object({
    payee: requiredString,
    accountId: z.number().nullable(),
    amount: positiveCents,
    dueDate: isoDate,
    categoryId: z.number().nullable(),
    notes: z.string().max(500, messages.max500).optional(),
  })
  .refine((d) => d.accountId !== null, {
    message: messages.required,
    path: ["accountId"],
  })

export type PlanPaymentValues = z.infer<typeof planPaymentSchema>
