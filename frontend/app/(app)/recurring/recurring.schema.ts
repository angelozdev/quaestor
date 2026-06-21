import { z } from "zod"
import { messages } from "@/lib/schemas/messages"
import { intervalCount, isoDate, positiveCents, requiredString } from "@/lib/schemas/primitives"

export const recurringCreateSchema = z
  .object({
    name: requiredString,
    payee: z.string().max(500, messages.max500).optional(),
    amount: positiveCents,
    currency: z.enum(["COP", "USD"], { message: messages.opcionInvalida }),
    categoryId: z.number().nullable(),
    accountId: z.number().nullable(),
    type: z.enum(["expense", "income"], { message: messages.opcionInvalida }),
    mode: z.enum(["auto", "manual"], { message: messages.opcionInvalida }),
    intervalCount,
    intervalUnit: z.enum(["day", "week", "month", "year"], { message: messages.opcionInvalida }),
    startDate: isoDate,
    endDate: isoDate.optional().or(z.literal("")),
  })
  .refine((d) => !d.endDate || d.endDate >= d.startDate, {
    message: messages.finDebeSerMayorOIgual,
    path: ["endDate"],
  })
  .refine((d) => d.accountId !== null, {
    message: messages.required,
    path: ["accountId"],
  })

export type RecurringCreateValues = z.infer<typeof recurringCreateSchema>
