"use client"

import { useForm as useTanStackForm } from "@tanstack/react-form"
import { useState } from "react"
import type { z } from "zod"
import {
  buildEntityFormSchema,
  type EntityFormValues,
} from "@/components/entity-form-dialog.schema"
import { EntitySelect } from "@/components/entity-select"
import { MoneyInput } from "@/components/money-input"
import { Button, Checkbox, Dialog, DialogPopup, DialogTitle, Input, Label, Select } from "@/ui"

export type Field =
  | {
      kind: "text"
      name: string
      label: string
      required?: boolean
      placeholder?: string
      disabled?: boolean
    }
  | {
      kind: "number"
      name: string
      label: string
      required?: boolean
      min?: number
      disabled?: boolean
    }
  | {
      kind: "select"
      name: string
      label: string
      options: { value: string; label: string }[]
      required?: boolean
      disabled?: boolean
    }
  | {
      kind: "entity"
      name: string
      label: string
      queryKey: readonly unknown[]
      queryFn: () => Promise<{ id: number; name: string }[]>
      allowNullLabel?: string
      disabled?: boolean
    }
  | { kind: "checkbox"; name: string; label: string }
  | {
      kind: "money"
      name: string
      label: string
      currencyFrom: string
      required?: boolean
      disabled?: boolean
    }

/**
 * @deprecated Prefer typing callers with their own zod schema via the `schema`
 * prop. Kept exported for backward compatibility with existing callers that
 * still pass un-validated `FormValues` records.
 */
export type FormValues = EntityFormValues

type Props<TValues extends EntityFormValues> = {
  open: boolean
  onOpenChange: (o: boolean) => void
  title: string
  fields: Field[]
  initialValues: TValues
  submitLabel?: string
  pending?: boolean
  /**
   * Optional zod schema for validation. When provided, `onChange` validation
   * runs against `initialValues`/`TValues`. When omitted, only the legacy
   * required-field check is applied (kept for backward compatibility).
   *
   * Typed as `z.ZodType<TValues, TValues>` so the schema's StandardSchemaV1
   * input AND output are both `TValues` — which is what TanStack Form's
   * `validators.onChange` (`StandardSchemaV1<TValues, unknown>`) expects.
   */
  schema?: z.ZodType<TValues, TValues>
  onSubmit: (values: TValues) => void
}

/**
 * Generic CRUD dialog used by categories, accounts, tags, and category-groups.
 * Migrated to TanStack Form (Task 43): when callers pass a `schema` prop, the
 * form runs zod validation on every change. The legacy `required`-based check
 * remains for callers that have not yet supplied a schema.
 */
export function EntityFormDialog<TValues extends EntityFormValues>({
  open,
  onOpenChange,
  title,
  fields,
  initialValues,
  submitLabel = "Guardar",
  pending = false,
  schema,
  onSubmit,
}: Props<TValues>) {
  // Auto-derive a permissive schema from the Field[] spec when callers don't
  // supply one. This keeps `useTanStackForm`'s `validators.onChange` non-null
  // so we get free required-field enforcement without touching existing call
  // sites that haven't authored a schema yet.
  const effectiveSchema = (schema ?? buildEntityFormSchema(fields)) as z.ZodType<TValues, TValues>

  const form = useTanStackForm({
    defaultValues: initialValues,
    validators: { onChange: effectiveSchema },
    onSubmit: async ({ value }) => {
      onSubmit(value)
    },
  })

  // Reseed whenever the dialog opens (create vs edit pass different initialValues).
  // Uses the derived-during-render pattern (recommended by React docs) instead
  // of useEffect to avoid the exhaustive-deps violation: tracking the previous
  // `open` value lets us reseed once on the open transition without depending
  // on the unstable `initialValues` reference.
  const [prevOpen, setPrevOpen] = useState(open)
  if (open !== prevOpen) {
    setPrevOpen(open)
    if (open) {
      form.reset(initialValues)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>{title}</DialogTitle>
        <form
          onSubmit={(e) => {
            e.preventDefault()
            e.stopPropagation()
            void form.handleSubmit()
          }}
          className="space-y-4"
        >
          {fields.map((f) => {
            const required = "required" in f && Boolean(f.required)
            return (
              <form.Field key={f.name} name={f.name}>
                {(field) => {
                  // `field.state.meta.errors` is typed by the form's validator;
                  // for zod schemas it carries StandardSchemaV1 issues but the
                  // generic typing collapses to `unknown` here, so we widen
                  // before narrowing.
                  const error = field.state.meta.errors[0] as unknown
                  const errorMessage =
                    typeof error === "string"
                      ? error
                      : error &&
                          typeof error === "object" &&
                          "message" in error &&
                          typeof (error as { message: unknown }).message === "string"
                        ? (error as { message: string }).message
                        : error
                          ? String(error)
                          : null
                  return (
                    <div className="space-y-1.5">
                      {f.kind !== "checkbox" && (
                        <Label htmlFor={f.name}>
                          {f.label}
                          {required && <span className="text-destructive"> *</span>}
                        </Label>
                      )}

                      {f.kind === "text" && (
                        <Input
                          id={f.name}
                          value={typeof field.state.value === "string" ? field.state.value : ""}
                          placeholder={f.placeholder}
                          disabled={f.disabled}
                          aria-invalid={errorMessage ? true : undefined}
                          onChange={(e) => field.handleChange(e.target.value as never)}
                          onBlur={field.handleBlur}
                        />
                      )}

                      {f.kind === "number" && (
                        <Input
                          id={f.name}
                          type="number"
                          min={f.min}
                          value={
                            typeof field.state.value === "number" &&
                            Number.isFinite(field.state.value)
                              ? String(field.state.value)
                              : ""
                          }
                          disabled={f.disabled}
                          aria-invalid={errorMessage ? true : undefined}
                          onChange={(e) => {
                            const raw = e.target.value
                            field.handleChange((raw === "" ? Number.NaN : Number(raw)) as never)
                          }}
                          onBlur={field.handleBlur}
                        />
                      )}

                      {f.kind === "select" && (
                        <Select
                          id={f.name}
                          value={typeof field.state.value === "string" ? field.state.value : null}
                          onValueChange={(v) => field.handleChange((v ?? "") as never)}
                          items={f.options}
                          disabled={f.disabled}
                        />
                      )}

                      {f.kind === "entity" && (
                        <EntitySelect
                          id={f.name}
                          value={typeof field.state.value === "number" ? field.state.value : null}
                          onChange={(v) => field.handleChange(v as never)}
                          queryKey={f.queryKey}
                          queryFn={f.queryFn}
                          allowNullLabel={f.allowNullLabel}
                          disabled={f.disabled}
                        />
                      )}

                      {f.kind === "money" && (
                        <MoneyInput
                          id={f.name}
                          currency={String(initialValues[f.currencyFrom] ?? "COP")}
                          value={
                            typeof field.state.value === "number" &&
                            Number.isFinite(field.state.value)
                              ? field.state.value
                              : null
                          }
                          disabled={f.disabled}
                          onChange={(cents) => field.handleChange(cents as never)}
                        />
                      )}

                      {f.kind === "checkbox" && (
                        <label htmlFor={f.name} className="flex items-center gap-2 text-sm">
                          <Checkbox
                            id={f.name}
                            checked={Boolean(field.state.value)}
                            onCheckedChange={(c) => field.handleChange(c as never)}
                          />
                          {f.label}
                        </label>
                      )}

                      {errorMessage && <p className="text-xs text-destructive">{errorMessage}</p>}
                    </div>
                  )
                }}
              </form.Field>
            )
          })}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={pending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={pending || form.state.isSubmitting}>
              {pending || form.state.isSubmitting ? "…" : submitLabel}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  )
}
