import { z } from "zod"
import { messages } from "@/lib/schemas/messages"
import { isoDate, optionalString } from "@/lib/schemas/primitives"

// Editable fields on an existing transaction: payee, date, category, notes, tags.
// Amount/account are intentionally not editable here — see the in-dialog hint.
const fields = {
  payee: z.string().trim().max(500, messages.max500).optional().or(z.literal("")),
  categoryId: z.number().nullable(),
  date: isoDate,
  notes: optionalString,
  tags: z.array(z.string()),
  metaId: z.number().nullable(),
}

/** A transfer carries no category and an expense or income must keep one, so
 * the rule the form enforces depends on which it is editing (ADR-0042). */
export const txEditSchema = (isTransfer: boolean) =>
  isTransfer
    ? z.object(fields).refine((d) => d.categoryId === null, {
        message: messages.transferenciaSinCategoria,
        path: ["categoryId"],
      })
    : z.object(fields).refine((d) => d.categoryId !== null, {
        message: messages.required,
        path: ["categoryId"],
      })

export type TransactionEditValues = z.infer<ReturnType<typeof txEditSchema>>
