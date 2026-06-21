import { z } from "zod"

/**
 * Common Spanish error messages shared across schema-level constraints
 * (`primitives.ts`) and the global zod error map below. All literal
 * Spanish strings live here; consumers should reference these constants
 * rather than re-declaring the same strings inline.
 */
export const messages = {
  required: "Requerido",
  soloNumeros: "Solo números",
  soloNumerosEnteros: "Solo números enteros",
  debeSerPositivo: "Debe ser > 0",
  debeSerNoNegativo: "Debe ser ≥ 0",
  formatoInvalido: "Formato inválido",
  fechaInvalida: "Fecha inválida (YYYY-MM-DD)",
  max120: "Máximo 120 caracteres",
  max500: "Máximo 500 caracteres",
  valorInvalido: "Valor inválido",
  opcionInvalida: "Opción inválida",
  demasiadoPequeno: "Valor demasiado pequeño",
  demasiadoGrande: "Valor demasiado grande",
  finDebeSerMayorOIgual: "Fin debe ser ≥ inicio",
} as const

/** Message for `z.number().min(n)` / `.nonnegative()` (n=0). */
export const minNumberMessage = (n: number): string => `Debe ser ≥ ${n}`

/** Message for `z.number().max(n)`. */
export const maxNumberMessage = (n: number): string => `Debe ser ≤ ${n}`

/**
 * Register a global Spanish error map for zod. Call once at app boot.
 * After this call, every `z.X.safeParse` returns issues with Spanish
 * `message` for the codes listed below; per-schema custom messages (e.g.
 * `z.number({ invalid_type_error: ... })`) still win because zod prefers
 * schema-level over global.
 */
export function registerZodMessages(): void {
  z.setErrorMap((issue, _ctx) => {
    switch (issue.code) {
      case z.ZodIssueCode.invalid_type:
        if (issue.received === "nan" || issue.expected === "number") {
          return { message: messages.soloNumeros }
        }
        return { message: messages.valorInvalido }
      case z.ZodIssueCode.invalid_string:
        return { message: messages.formatoInvalido }
      case z.ZodIssueCode.too_small:
        if (issue.type === "string" && issue.minimum === 1) {
          return { message: messages.required }
        }
        if (issue.type === "number" && issue.minimum === 1) {
          return { message: minNumberMessage(1) }
        }
        if (issue.type === "number" && issue.minimum === 0) {
          return { message: minNumberMessage(0) }
        }
        return { message: messages.demasiadoPequeno }
      case z.ZodIssueCode.too_big:
        return { message: messages.demasiadoGrande }
      case z.ZodIssueCode.invalid_enum_value:
        return { message: messages.opcionInvalida }
      default:
        return { message: messages.valorInvalido }
    }
  })
}

// Module-level singleton: runs on first import, before any schema is parsed.
registerZodMessages()
