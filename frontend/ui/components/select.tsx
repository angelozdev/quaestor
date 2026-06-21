"use client"

import { Select as SelectPrimitive } from "@base-ui/react/select"
import { Check, ChevronsUpDown } from "lucide-react"
import { cn } from "../lib/cn"

export interface SelectItem {
  value: string
  label: string
}

export interface SelectProps {
  value: string | null
  onValueChange: (value: string | null) => void
  items: SelectItem[]
  placeholder?: string
  disabled?: boolean
  id?: string
  "aria-label"?: string
  className?: string
}

function Select({
  value,
  onValueChange,
  items,
  placeholder = "Selecciona…",
  disabled,
  id,
  className,
  "aria-label": ariaLabel,
}: SelectProps) {
  const labelFor = (v: string | null) => items.find((it) => it.value === v)?.label ?? null
  return (
    <SelectPrimitive.Root
      value={value}
      onValueChange={(v) => onValueChange(v)}
      disabled={disabled}
      items={items.reduce<Record<string, string>>((acc, it) => {
        acc[it.value] = it.label
        return acc
      }, {})}
    >
      <SelectPrimitive.Trigger
        id={id}
        aria-label={ariaLabel}
        data-slot="select-trigger"
        className={cn(
          "flex h-8 w-full items-center justify-between gap-2 rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50 data-[popup-open]:border-ring",
          className,
        )}
      >
        <SelectPrimitive.Value>
          {(v: string | null) =>
            labelFor(v) ?? <span className="text-muted-foreground">{placeholder}</span>
          }
        </SelectPrimitive.Value>
        <SelectPrimitive.Icon>
          <ChevronsUpDown className="size-4 text-muted-foreground" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>

      <SelectPrimitive.Portal>
        <SelectPrimitive.Positioner sideOffset={4} className="z-50">
          <SelectPrimitive.Popup className="max-h-72 min-w-[var(--anchor-width)] overflow-y-auto rounded-lg border border-border bg-popover p-1 text-sm shadow-md outline-none">
            {items.map((it) => (
              <SelectPrimitive.Item
                key={it.value}
                value={it.value}
                className="flex cursor-default items-center justify-between gap-2 rounded-md px-2 py-1.5 outline-none data-[highlighted]:bg-muted"
              >
                <SelectPrimitive.ItemText>{it.label}</SelectPrimitive.ItemText>
                <SelectPrimitive.ItemIndicator>
                  <Check className="size-4" />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Popup>
        </SelectPrimitive.Positioner>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  )
}

export { Select }
