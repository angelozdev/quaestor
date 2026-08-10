import { formatCents } from "@/lib/money"

/**
 * The reading form every figure-bearing screen is built from.
 *
 * A `Section` names a subject, a `Term` is one label and its amount, and a
 * `Total` closes a run of terms under a rule. Together they are the Liquidation
 * of DESIGN.md: a total always sits next to the terms it was folded from, with
 * nothing to click.
 *
 * A section's name is the Title rung of the type scale, one full step above the
 * Label rung its column heads and controls use. At the same size it read as a
 * sibling of the column heads and the page stopped having levels — the second
 * thing the owner reported. `says` glosses the subject, `badge` qualifies it,
 * and `aside` carries a control that belongs to it.
 *
 * These know nothing about money's meaning — direction, currency and colour are
 * the caller's, through `MoneyAmount` or its own node.
 */
export function Section({
  label,
  says,
  badge,
  aside,
  headingId,
  children,
  className = "",
}: {
  label: string
  says?: string
  badge?: React.ReactNode
  aside?: React.ReactNode
  headingId?: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <section aria-labelledby={headingId} className={`space-y-3 ${className}`}>
      <div
        className="flex items-start justify-between gap-4 border-b pb-2"
        style={{ borderColor: "var(--border)" }}
      >
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h2 id={headingId} className="text-[0.9375rem] font-semibold leading-[1.4]">
              {label}
            </h2>
            {badge}
          </div>
          {says && (
            <p className="mt-0.5 text-sm" style={{ color: "var(--muted-foreground)" }}>
              {says}
            </p>
          )}
        </div>
        {aside && <div className="shrink-0">{aside}</div>}
      </div>
      {children}
    </section>
  )
}

export function Term({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <span className="min-w-0 truncate text-sm" style={{ color: "var(--muted-foreground)" }}>
        {label}
      </span>
      {children}
    </div>
  )
}

export function Total({
  label,
  cents,
  currency = "COP",
}: {
  label: string
  cents: number
  currency?: string
}) {
  return (
    <div className="hairline-total mt-1 flex items-baseline justify-between gap-4 pt-2">
      <span className="text-sm font-semibold">{label}</span>
      <span className="text-sm font-semibold tabular-nums">{formatCents(cents, currency)}</span>
    </div>
  )
}

/**
 * The muted operator that says a term is subtracted.
 *
 * It is a glyph of its own rather than a sign inside the amount, so the figure's
 * text stays exactly what the acceptance contract reads (AC-4) while the column
 * still shows its arithmetic.
 */
export function Minus() {
  return (
    <span aria-hidden className="text-xs" style={{ color: "var(--muted-foreground)" }}>
      −
    </span>
  )
}
