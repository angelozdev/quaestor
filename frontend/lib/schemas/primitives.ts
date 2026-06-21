import { z } from "zod"

/** Integer cents >= 0. Used for balances and zero-allowed amounts. */
export const nonNegativeCents = z
  .number({ invalid_type_error: "Solo números" })
  .int("Solo números enteros")
  .nonnegative("Debe ser ≥ 0")

/** Integer cents > 0. Used for expenses, income, transfers, contributions. */
export const positiveCents = z
  .number({ invalid_type_error: "Solo números" })
  .int("Solo números enteros")
  .positive("Debe ser > 0")

/** Recurring interval count: integer 1..1000. */
export const intervalCount = z
  .number({ invalid_type_error: "Solo números" })
  .int("Solo números enteros")
  .min(1, "Debe ser ≥ 1")
  .max(1000, "Debe ser ≤ 1000")

/** USD→COP rate: float (0, 100000]. */
export const fxRate = z
  .number({ invalid_type_error: "Solo números" })
  .positive("Debe ser > 0")
  .max(100_000, "Debe ser ≤ 100000")

/** ISO date string YYYY-MM-DD. Native <input type="date"> produces this. */
export const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "Fecha inválida (YYYY-MM-DD)")

/** Required, trimmed, non-empty string with sane length. */
export const requiredString = z
  .string()
  .trim()
  .min(1, "Requerido")
  .max(120, "Máximo 120 caracteres")

/** Optional free-form string, trimmed, capped. */
export const optionalString = z
  .string()
  .trim()
  .max(500, "Máximo 500 caracteres")
  .optional()
