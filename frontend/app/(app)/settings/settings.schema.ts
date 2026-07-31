import { z } from "zod"
import { fxRate } from "@/lib/schemas/primitives"

export const setTrmSchema = z.object({
  usdCop: fxRate,
})

export type SetTrmValues = z.infer<typeof setTrmSchema>
