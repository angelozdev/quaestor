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
      case "invalid_type":
        if (issue.expected === "number") return { message: "Solo números" }
        return { message: "Valor inválido" }
      case "invalid_format":
        return { message: "Formato inválido" }
      case "too_small":
        if (issue.origin === "string" && issue.minimum === 1) return { message: "Requerido" }
        if (issue.origin === "number" && issue.minimum === 1) return { message: "Debe ser ≥ 1" }
        if (issue.origin === "number" && issue.minimum === 0) return { message: "Debe ser ≥ 0" }
        return { message: "Valor demasiado pequeño" }
      case "too_big":
        return { message: "Valor demasiado grande" }
      case "invalid_value":
        return { message: "Opción inválida" }
      default:
        return { message: "Valor inválido" }
    }
  })
}

// Module-level singleton: runs on first import, before any schema is parsed.
registerZodMessages()
