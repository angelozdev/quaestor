import Link from "next/link"
import type { ReactNode } from "react"

export type Action = { label: string; href?: string; onClick?: () => void }

const WAY_IN_CLASS = "text-xs px-3 py-1.5 rounded-md border transition-colors"
const WAY_IN_STYLE = { borderColor: "var(--border)", color: "var(--foreground)" } as const

function WayIn({ label, href, onClick }: Action) {
  return href ? (
    <Link href={href} className={WAY_IN_CLASS} style={WAY_IN_STYLE}>
      {label}
    </Link>
  ) : (
    <button type="button" onClick={onClick} className={WAY_IN_CLASS} style={WAY_IN_STYLE}>
      {label}
    </button>
  )
}

/**
 * A screen with nothing on it yet.
 *
 * `message` is the label; `description` is what the thing is and what it is
 * good for, which is what makes the empty screen teach instead of announce.
 *
 * `action` is the way in, or the ways in where the screen holds more than one
 * kind of thing and the owner has just read what each kind is.
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
  action?: Action | Action[]
}) {
  const waysIn = action === undefined ? [] : Array.isArray(action) ? action : [action]
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
      {waysIn.length > 0 ? (
        <div className="flex flex-wrap items-center justify-center gap-2">
          {waysIn.map((wayIn) => (
            <WayIn key={wayIn.label} {...wayIn} />
          ))}
        </div>
      ) : null}
    </div>
  )
}
