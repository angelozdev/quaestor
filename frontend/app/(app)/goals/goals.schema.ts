import { z } from "zod"
import { isoDate, nonNegativeCents, positiveCents, requiredString } from "@/lib/schemas/primitives"

// Create + edit share the same shape. The page drives which fields are required
// at the UI level (e.g. savings account only on create). Both target and
// deadline must be set together for a defined goal, or both empty for an
// open-ended goal; the cross-field rule encodes that invariant.
export const goalUpsertSchema = z
  .object({
    name: requiredString,
    monthlyAmount: positiveCents,
    savingsAccountId: z.number().nullable(),
    targetAmount: nonNegativeCents.optional().or(z.literal(Number.NaN)),
    deadline: isoDate.optional().or(z.literal("")),
  })
  .refine((d) => d.savingsAccountId !== null, {
    message: "Requerido",
    path: ["savingsAccountId"],
  })
  .refine(
    (d) => {
      const targetSet = d.targetAmount !== undefined && Number.isFinite(d.targetAmount)
      const deadlineSet = typeof d.deadline === "string" && d.deadline.length > 0
      return targetSet === deadlineSet
    },
    {
      message: "Objetivo y fecha deben ir juntos",
      path: ["targetAmount"],
    },
  )

export type GoalUpsertValues = z.infer<typeof goalUpsertSchema>

// Contribute dialog: amount + date, both required.
export const contributeGoalSchema = z.object({
  amount: positiveCents,
  date: isoDate,
})

export type ContributeGoalValues = z.infer<typeof contributeGoalSchema>
