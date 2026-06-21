"use client"

import type { Control, FieldPath, FieldValues } from "react-hook-form"
import { useController } from "react-hook-form"
import { Input, Label } from "@/ui"

type Props<T extends FieldValues> = {
  control: Control<T>
  name: FieldPath<T>
  label: string
  type?: "text" | "number" | "date"
  placeholder?: string
  disabled?: boolean
  min?: number
  valueAsNumber?: boolean
}

/**
 * <Label> + <Input> + inline error. Bridges react-hook-form's `useController`
 * with our `Input` component. Use `valueAsNumber` for `<input type="number">`
 * so pasted "12abc" becomes NaN and zod rejects it.
 */
export function FormField<T extends FieldValues>({
  control,
  name,
  label,
  type = "text",
  placeholder,
  disabled,
  min,
  valueAsNumber,
}: Props<T>) {
  const {
    field,
    fieldState: { error },
  } = useController({ control, name })

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
            ? Number.isNaN(field.value)
              ? ""
              : String(field.value)
            : ((field.value as string | number | undefined) ?? "")
        }
        onChange={(e) => {
          if (valueAsNumber) {
            const raw = e.target.value
            field.onChange(raw === "" ? Number.NaN : Number(raw))
          } else {
            field.onChange(e.target.value)
          }
        }}
        onBlur={field.onBlur}
        ref={field.ref}
        aria-invalid={error ? true : undefined}
      />
      {error?.message && <p className="text-xs text-destructive">{error.message}</p>}
    </div>
  )
}