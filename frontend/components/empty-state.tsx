import Link from "next/link"
import type { ReactNode } from "react"

type Action = { label: string; href?: string; onClick?: () => void }

/**
 * A screen with nothing on it yet.
 *
 * `message` is the label; `description` is what the thing is and what it is
 * good for, which is what makes the empty screen teach instead of announce.
 */
export function EmptyState({
  message,
  description,
  icon,
  action,
}: {
  message: string
  description?: ReactNode
  icon?: ReactNode
  action?: Action
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center">
      {icon ? <div style={{ color: "var(--muted-foreground)" }}>{icon}</div> : null}
      {description ? (
        <>
          <p className="text-sm font-medium">{message}</p>
          <div
            className="max-w-prose space-y-1.5 text-sm"
            style={{ color: "var(--muted-foreground)" }}
          >
            {description}
          </div>
        </>
      ) : (
        <p className="text-sm" style={{ color: "var(--muted-foreground)" }}>
          {message}
        </p>
      )}
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
