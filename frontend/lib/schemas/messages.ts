import { z } from "zod"

/**
 * Register a global Spanish error map for zod. Call once at app boot
 * (Providers). After this call, every `z.X.safeParse` returns issues
 * with Spanish `message` for the codes listed below; per-schema custom
 * messages (e.g. `z.number({ invalid_type_error: ... })`) still win
 * because zod prefers schema-level over global.
 */
export function registerZodMessages(): void {
  z.setErrorMap((issue, _ctx) => {
    switch (issue.code) {
      case z.ZodIssueCode.invalid_type:
        if (issue.received === "nan") return { message: "Solo números" }
        if (issue.expected === "number") return { message: "Solo números" }
        return { message: "Valor inválido" }
      case z.ZodIssueCode.invalid_string:
        return { message: "Formato inválido" }
      case z.ZodIssueCode.too_small:
        if (issue.type === "string" && issue.minimum === 1) return { message: "Requerido" }
        if (issue.type === "number" && issue.minimum === 1) return { message: "Debe ser ≥ 1" }
        if (issue.type === "number" && issue.minimum === 0) return { message: "Debe ser ≥ 0" }
        return { message: "Valor demasiado pequeño" }
      case z.ZodIssueCode.too_big:
        return { message: "Valor demasiado grande" }
      case z.ZodIssueCode.invalid_enum_value:
        return { message: "Opción inválida" }
      default:
        return { message: "Valor inválido" }
    }
  })
}

// Module-level singleton: runs on first import, before any schema is parsed.
registerZodMessages()
