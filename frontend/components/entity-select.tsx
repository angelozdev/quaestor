"use client"

import { useQuery } from "@tanstack/react-query"
import { Select } from "@/ui"

const NULL_VALUE = "__null__"

export function EntitySelect({
  value,
  onChange,
  queryKey,
  queryFn,
  placeholder = "Selecciona…",
  allowNullLabel,
  disabled,
  id,
}: {
  value: number | null
  onChange: (id: number | null) => void
  queryKey: readonly unknown[]
  queryFn: () => Promise<{ id: number; name: string }[]>
  placeholder?: string
  allowNullLabel?: string
  disabled?: boolean
  id?: string
}) {
  const { data, isLoading } = useQuery({ queryKey, queryFn })

  const items = [
    ...(allowNullLabel ? [{ value: NULL_VALUE, label: allowNullLabel }] : []),
    ...(data ?? []).map((e) => ({ value: String(e.id), label: e.name })),
  ]

  return (
    <Select
      id={id}
      value={value === null ? (allowNullLabel ? NULL_VALUE : null) : String(value)}
      onValueChange={(v) => onChange(v === null || v === NULL_VALUE ? null : Number(v))}
      items={items}
      placeholder={isLoading ? "Cargando…" : placeholder}
      disabled={disabled || isLoading}
    />
  )
}
