"use client"

import { Input, Label } from "@/ui"

// `FieldApi` from @tanstack/react-form is a deeply generic class (parent data
// + on-mount/on-change/on-blur/on-submit/async/dynamic validators). It is
// impractical to thread through a presentational component, so we accept
// `any` and access only the documented render-prop surface. This matches the
// upstream `AnyFieldApi` idiom used in TanStack's own examples.
type Props = {
  // biome-ignore lint/suspicious/noExplicitAny: see file header.
  field: any
  label: string
  type?: "text" | "number" | "date"
  placeholder?: string
  disabled?: boolean
  min?: number
  valueAsNumber?: boolean
}

/**
 * <Label> + <Input> + inline error. Bridges TanStack Form's render-prop
 * `field` API with our `Input` component. Use `valueAsNumber` for
 * `<input type="number">` so pasted "12abc" becomes NaN and zod rejects it.
 */
export function FormField({
  field,
  label,
  type = "text",
  placeholder,
  disabled,
  min,
  valueAsNumber,
}: Props) {
  const error = field.state.meta.errors[0]
  // zod (StandardSchemaV1) issues arrive as { message, path } objects; custom
  // validators may pass plain strings. Handle both, then fall back to toString.
  const errorMessage =
    typeof error === "string"
      ? error
      : error &&
          typeof error === "object" &&
          "message" in error &&
          typeof error.message === "string"
        ? error.message
        : error
          ? String(error)
          : null
  return (
    <div className="space-y-1.5">
      <Label htmlFor={field.name}>
        {label}
        <span className="text-destructive"> *</span>
      </Label>
      <Input
        id={field.name}
        type={type}
        placeholder={placeholder}
        disabled={disabled}
        min={min}
        value={
          valueAsNumber
            ? typeof field.state.value === "number" && Number.isFinite(field.state.value)
              ? String(field.state.value)
              : ""
            : typeof field.state.value === "string" || typeof field.state.value === "number"
              ? field.state.value
              : ""
        }
        onChange={(e) => {
          if (valueAsNumber) {
            const raw = e.target.value
            field.handleChange(raw === "" ? Number.NaN : Number(raw))
          } else {
            field.handleChange(e.target.value)
          }
        }}
        onBlur={field.handleBlur}
        aria-invalid={errorMessage ? true : undefined}
      />
      {errorMessage && <p className="text-xs text-destructive">{errorMessage}</p>}
    </div>
  )
}
