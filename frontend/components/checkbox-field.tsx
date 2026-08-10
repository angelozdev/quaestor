"use client"

import { Checkbox } from "@/ui"

/**
 * A checkbox and the words that name it, tied together.
 *
 * The tie is `htmlFor`/`id`, not nesting: the control renders as a button, so
 * nesting alone leaves the label with nothing associated and clicking the words
 * does nothing. Four screens wrote this pair by hand and all four had that
 * defect.
 */
export function CheckboxField({
  id,
  label,
  checked,
  onCheckedChange,
  disabled,
}: {
  id: string
  label: string
  checked: boolean
  onCheckedChange: (checked: boolean) => void
  disabled?: boolean
}) {
  return (
    <div className="flex items-center gap-2">
      <Checkbox id={id} checked={checked} onCheckedChange={onCheckedChange} disabled={disabled} />
      <label htmlFor={id} className="text-sm" style={{ color: "var(--muted-foreground)" }}>
        {label}
      </label>
    </div>
  )
}
