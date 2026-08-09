import { z } from "zod"
import { messages } from "@/lib/schemas/messages"
import { categoryChosen, isoDate, positiveCents, requiredString } from "@/lib/schemas/primitives"

export const planPaymentSchema = z
  .object({
    payee: requiredString,
    accountId: z.number().nullable(),
    amount: positiveCents,
    dueDate: isoDate,
    categoryId: z.number().nullable(),
    newCategory: z.string().trim().max(120, messages.max120),
    metaId: z.number().nullable(),
    notes: z.string().max(500, messages.max500).optional(),
  })
  .refine((d) => d.accountId !== null, {
    message: messages.required,
    path: ["accountId"],
  })
  .superRefine(categoryChosen)

export type PlanPaymentValues = z.infer<typeof planPaymentSchema>
