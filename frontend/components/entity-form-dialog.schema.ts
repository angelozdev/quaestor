import { z } from "zod"
import { messages } from "@/lib/schemas/messages"

/**
 * Generic zod schemas for the CRUD dialog used by categories, accounts, tags,
 * and category-groups. The dialog accepts any zod object schema whose shape
 * matches the `fields` it was given; this module exports a small helper for
 * callers that want to build a schema from a `Field[]` spec.
 *
 * The generic dialog is intentionally permissive: callers can pass a hand-
 * written zod schema (e.g. for stricter constraints the auto-builder doesn't
 * express) and the dialog will use it for `onChange` validation. The
 * `buildEntityFormSchema` helper is a convenience for the common case.
 */
export type EntityFormValues = Record<string, string | number | boolean | null>

/**
 * Build a permissive zod object schema from a list of `Field` specs. Each
 * field kind maps to a sensible primitive:
 *
 * - text       → string (trimmed, optional unless `required`)
 * - number     → number (optional unless `required`)
 * - select     → string (optional unless `required`)
 * - entity     → number | null
 * - checkbox   → boolean
 * - money      → number | null (cents; non-negative integer)
 *
 * Callers that need tighter constraints (e.g. minimum balance, regex on name)
 * should hand-write a zod object schema instead of relying on this builder.
 *
 * The helper is generic over the desired output type so the dialog's
 * `validators.onChange` slot (which expects `StandardSchemaV1<TValues, _>`)
 * receives a schema whose input/output both line up with `TValues`.
 */
export function buildEntityFormSchema<TValues extends EntityFormValues>(
  // biome-ignore lint/suspicious/noExplicitAny: the Field union is local to entity-form-dialog.tsx; we deliberately erase shape here.
  fields: any[],
): z.ZodType<TValues, TValues> {
  // biome-ignore lint/suspicious/noExplicitAny: dynamic shape mirroring `fields`
  const shape: Record<string, any> = {}
  for (const f of fields) {
    const required = "required" in f && f.required
    switch (f.kind) {
      case "text":
        shape[f.name] = required
          ? z.string().trim().min(1, messages.required).max(120, messages.max120)
          : z.string().trim().max(120, messages.max120).optional()
        break
      case "number":
        shape[f.name] = required
          ? z.number({ error: messages.soloNumeros })
          : z.number({ error: messages.soloNumeros }).optional()
        break
      case "select":
        shape[f.name] = required ? z.string().min(1, messages.required) : z.string().optional()
        break
      case "entity":
        shape[f.name] = z.number().nullable()
        break
      case "money":
        shape[f.name] = z
          .number({ error: messages.soloNumeros })
          .int(messages.soloNumerosEnteros)
          .nullable()
        break
      case "checkbox":
        shape[f.name] = z.boolean()
        break
    }
  }
  return z.object(shape) as unknown as z.ZodType<TValues, TValues>
}
