import { z } from "zod"
import { fxRate, isoDate } from "@/lib/schemas/primitives"

export const setFxRateSchema = z.object({
  date: isoDate,
  usdCop: fxRate,
})

export type SetFxRateValues = z.infer<typeof setFxRateSchema>
