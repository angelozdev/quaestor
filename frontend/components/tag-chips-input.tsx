"use client"

import { useId, useState } from "react"
import { Badge, Button, Input, Label } from "@/ui"

export function TagChipsInput({
  value,
  onChange,
  suggestions = [],
  label = "Etiquetas",
}: {
  value: string[]
  onChange: (tags: string[]) => void
  suggestions?: string[]
  label?: string
}) {
  const [draft, setDraft] = useState("")
  const inputId = useId()

  function add(name: string) {
    const trimmed = name.trim()
    setDraft("")
    if (!trimmed || value.includes(trimmed)) return
    onChange([...value, trimmed])
  }

  const query = draft.trim().toLowerCase()
  const matches =
    query.length > 0
      ? suggestions.filter((s) => s.toLowerCase().includes(query) && !value.includes(s))
      : []

  return (
    <div className="space-y-1.5">
      <Label htmlFor={inputId}>{label}</Label>
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((tag) => (
            <Badge key={tag} variant="secondary">
              {tag}
              <button
                type="button"
                aria-label={`Quitar etiqueta ${tag}`}
                className="cursor-pointer"
                onClick={() => onChange(value.filter((t) => t !== tag))}
              >
                ×
              </button>
            </Badge>
          ))}
        </div>
      )}
      <Input
        id={inputId}
        value={draft}
        placeholder="Añadir etiqueta…"
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault()
            add(draft)
          }
        }}
      />
      {matches.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {matches.map((name) => (
            <Button key={name} type="button" variant="outline" size="xs" onClick={() => add(name)}>
              {name}
            </Button>
          ))}
        </div>
      )}
    </div>
  )
}
