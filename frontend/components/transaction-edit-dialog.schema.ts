import { z } from "zod"
import { messages } from "@/lib/schemas/messages"
import { isoDate, optionalString } from "@/lib/schemas/primitives"

// Editable fields on an existing transaction: payee, date, category, notes, tags.
// Amount/account are intentionally not editable here — see the in-dialog hint.
export const txEditSchema = z.object({
  payee: z.string().trim().max(500, messages.max500).optional().or(z.literal("")),
  categoryId: z.number().nullable(),
  date: isoDate,
  notes: optionalString,
  tags: z.array(z.string()),
})

export type TransactionEditValues = z.infer<typeof txEditSchema>
