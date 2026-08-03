/**
 * Centralized Spanish error strings + parameterized helpers. Single source of
 * truth for every Spanish error message used by zod schemas in this project.
 *
 * Forms import these constants and pass them to zod's chain-level message
 * options (e.g. `.min(1, messages.required)`). No global error map is
 * registered — each form is responsible for its own validation.
 */

export const messages = {
  required: "Requerido",
  soloNumeros: "Solo números",
  soloNumerosEnteros: "Solo números enteros",
  debeSerPositivo: "Debe ser > 0",
  formatoInvalido: "Formato inválido",
  fechaInvalida: "Fecha inválida (YYYY-MM-DD)",
  max120: "Máximo 120 caracteres",
  max500: "Máximo 500 caracteres",
  valorInvalido: "Valor inválido",
  opcionInvalida: "Opción inválida",
  demasiadoPequeno: "Valor demasiado pequeño",
  demasiadoGrande: "Valor demasiado grande",
  finDebeSerMayorOIgual: "Fin debe ser ≥ inicio",
  mesInvalido: "Mes inválido",
  categoriaAmbigua: "Elegí una categoría o creá una, no las dos",
  transferenciaSinCategoria: "Una transferencia no lleva categoría",
} as const

/** `Debe ser ≥ N` — use with zod `.min(n, ...)`. */
export const minNumberMessage = (n: number): string => `Debe ser ≥ ${n}`

/** `Debe ser ≤ N` — use with zod `.max(n, ...)`. */
export const maxNumberMessage = (n: number): string => `Debe ser ≤ ${n}`
