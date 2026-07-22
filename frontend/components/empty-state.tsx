import Link from "next/link"
import type { ReactNode } from "react"

type Action = { label: string; href?: string; onClick?: () => void }

export function EmptyState({
  message,
  icon,
  action,
}: {
  message: string
  icon?: ReactNode
  action?: Action
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center">
      {icon ? <div style={{ color: "var(--muted-foreground)" }}>{icon}</div> : null}
      <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
        {message}
      </p>
      {action ? (
        action.href ? (
          <Link
            href={action.href}
            className="text-xs px-3 py-1.5 rounded-md border transition-colors"
            style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
          >
            {action.label}
          </Link>
        ) : (
          <button
            type="button"
            onClick={action.onClick}
            className="text-xs px-3 py-1.5 rounded-md border transition-colors"
            style={{ borderColor: "var(--border)", color: "var(--foreground)" }}
          >
            {action.label}
          </button>
        )
      ) : null}
    </div>
  )
}
