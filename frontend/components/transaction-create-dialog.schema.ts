import { z } from "zod"
import { messages } from "@/lib/schemas/messages"
import { fxRate, isoDate, optionalString, positiveCents } from "@/lib/schemas/primitives"

// Normal tab: expense/income transaction. The category field is an ID
// (number | null) selected via EntitySelect, matching the existing UI.
export const txNormalSchema = z
  .object({
    type: z.enum(["expense", "income"], { message: messages.opcionInvalida }),
    accountId: z.number().nullable(),
    amount: positiveCents,
    categoryId: z.number().nullable(),
    date: isoDate,
    payee: z.string().trim().max(500, messages.max500).optional().or(z.literal("")),
    fxRate: fxRate.optional().or(z.literal(Number.NaN)),
    notes: optionalString,
  })
  .refine((d) => d.accountId !== null, {
    message: messages.required,
    path: ["accountId"],
  })

export type TxNormalValues = z.infer<typeof txNormalSchema>

// Transfer tab: between two accounts. Amount/date/from/to required.
export const txTransferSchema = z
  .object({
    fromId: z.number().nullable(),
    toId: z.number().nullable(),
    amount: positiveCents,
    date: isoDate,
    fxRate: fxRate.optional().or(z.literal(Number.NaN)),
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
