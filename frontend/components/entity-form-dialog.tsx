"use client"

import { useState } from "react"
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

export type FormValues = Record<string, string | number | boolean | null>

export function EntityFormDialog({
  open,
  onOpenChange,
  title,
  fields,
  initialValues,
  submitLabel = "Guardar",
  pending = false,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (o: boolean) => void
  title: string
  fields: Field[]
  initialValues: FormValues
  submitLabel?: string
  pending?: boolean
  onSubmit: (values: FormValues) => void
}) {
  const [values, setValues] = useState<FormValues>(initialValues)
  const [touched, setTouched] = useState(false)

  // Reseed whenever the dialog opens (create vs edit pass different initialValues).
  // Uses the derived-during-render pattern (recommended by React docs) instead
  // of useEffect to avoid the exhaustive-deps violation: tracking the previous
  // `open` value lets us reseed once on the open transition without depending
  // on the unstable `initialValues` reference.
  const [prevOpen, setPrevOpen] = useState(open)
  if (open !== prevOpen) {
    setPrevOpen(open)
    if (open) {
      setValues(initialValues)
      setTouched(false)
    }
  }

  const set = (name: string, v: FormValues[string]) => setValues((prev) => ({ ...prev, [name]: v }))

  const missingRequired = fields.some((f) => {
    if (!("required" in f) || !f.required) return false
    const v = values[f.name]
    return v === null || v === undefined || v === ""
  })

  function submit(e: React.FormEvent) {
    e.preventDefault()
    setTouched(true)
    if (missingRequired) return
    onSubmit(values)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPopup>
        <DialogTitle>{title}</DialogTitle>
        <form onSubmit={submit} className="space-y-4">
          {fields.map((f) => {
            const invalid =
              touched &&
              "required" in f &&
              f.required &&
              (values[f.name] === null || values[f.name] === "")
            return (
              <div key={f.name} className="space-y-1.5">
                {f.kind !== "checkbox" && (
                  <Label htmlFor={f.name}>
                    {f.label}
                    {"required" in f && f.required && <span className="text-destructive"> *</span>}
                  </Label>
                )}

                {f.kind === "text" && (
                  <Input
                    id={f.name}
                    value={(values[f.name] as string) ?? ""}
                    placeholder={f.placeholder}
                    disabled={f.disabled}
                    aria-invalid={invalid || undefined}
                    onChange={(e) => set(f.name, e.target.value)}
                  />
                )}

                {f.kind === "number" && (
                  <Input
                    id={f.name}
                    type="number"
                    min={f.min}
                    value={values[f.name] === null ? "" : String(values[f.name])}
                    disabled={f.disabled}
                    aria-invalid={invalid || undefined}
                    onChange={(e) =>
                      set(f.name, e.target.value === "" ? null : Number(e.target.value))
                    }
                  />
                )}

                {f.kind === "select" && (
                  <Select
                    id={f.name}
                    value={(values[f.name] as string) ?? null}
                    onValueChange={(v) => set(f.name, v)}
                    items={f.options}
                    disabled={f.disabled}
                  />
                )}

                {f.kind === "entity" && (
                  <EntitySelect
                    id={f.name}
                    value={(values[f.name] as number | null) ?? null}
                    onChange={(id) => set(f.name, id)}
                    queryKey={f.queryKey}
                    queryFn={f.queryFn}
                    allowNullLabel={f.allowNullLabel}
                    disabled={f.disabled}
                  />
                )}

                {f.kind === "money" && (
                  <MoneyInput
                    id={f.name}
                    currency={(values[f.currencyFrom] as string) ?? "COP"}
                    value={(values[f.name] as number | null) ?? null}
                    disabled={f.disabled}
                    onChange={(cents) => set(f.name, cents)}
                  />
                )}

                {f.kind === "checkbox" && (
                  <label htmlFor={f.name} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      id={f.name}
                      checked={Boolean(values[f.name])}
                      onCheckedChange={(c) => set(f.name, c)}
                    />
                    {f.label}
                  </label>
                )}
              </div>
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
            <Button type="submit" disabled={pending || missingRequired}>
              {pending ? "…" : submitLabel}
            </Button>
          </div>
        </form>
      </DialogPopup>
    </Dialog>
  )
}
