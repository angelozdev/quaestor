import { z } from "zod"
import { messages } from "@/lib/schemas/messages"
import { categoryChosen, isoDate, optionalString, positiveCents } from "@/lib/schemas/primitives"

export const txNormalSchema = z
  .object({
    type: z.enum(["expense", "income"], { message: messages.opcionInvalida }),
    accountId: z.number().nullable(),
    amount: positiveCents,
    categoryId: z.number().nullable(),
    newCategory: z.string().trim().max(120, messages.max120),
    date: isoDate,
    payee: z.string().trim().max(500, messages.max500).optional().or(z.literal("")),
    notes: optionalString,
    tags: z.array(z.string()),
  })
  .refine((d) => d.accountId !== null, {
    message: messages.required,
    path: ["accountId"],
  })
  .superRefine(categoryChosen)

export type TxNormalValues = z.infer<typeof txNormalSchema>

export const txTransferSchema = z
  .object({
    fromId: z.number().nullable(),
    toId: z.number().nullable(),
    amount: positiveCents,
    amountReceived: positiveCents.optional().or(z.literal(Number.NaN)),
    date: isoDate,
    notes: optionalString,
  })
  .refine((d) => d.fromId !== null, {
    message: messages.required,
    path: ["fromId"],
  })
  .refine((d) => d.toId !== null, {
    message: messages.required,
    path: ["toId"],
  })

export type TxTransferValues = z.infer<typeof txTransferSchema>
