"use client"

import { Button } from "@/ui"

export type Scope = "week" | "month"

const LABEL: Record<Scope, string> = {
  week: "Esta semana",
  month: "Este mes",
}

/**
 * The window a pending-payments figure answers for.
 *
 * The dashboard widget and the Por pagar screen ask the same question, so they
 * ask it with the same control rather than two copies that drift apart.
 */
export function ScopePicker({
  scope,
  onPick,
  className = "",
}: {
  scope: Scope
  onPick: (scope: Scope) => void
  className?: string
}) {
  return (
    <div
      className={`inline-flex items-center gap-1 rounded-md p-0.5 ${className}`}
      style={{ background: "var(--muted)" }}
    >
      {(Object.keys(LABEL) as Scope[]).map((s) => (
        <Button
          key={s}
          type="button"
          size="xs"
          variant={scope === s ? "outline" : "ghost"}
          onClick={() => onPick(s)}
          className={scope === s ? "rounded" : "rounded text-muted-foreground"}
        >
          {LABEL[s]}
        </Button>
      ))}
    </div>
  )
}
