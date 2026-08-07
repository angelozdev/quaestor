/**
 * The title row every screen opens with.
 *
 * `help` is the "¿Cómo funciona esto?" control and sits last, flush with the
 * right edge, so it is in the same place on every screen (AC-7). Below the
 * `sm` breakpoint the row stacks instead: the controls of a screen like Fondos
 * y presupuestos are wider than a phone, and side by side they would push the
 * page sideways (AC-14).
 */
export function PageHeader({
  title,
  subtitle,
  action,
  help,
}: {
  title: string
  subtitle?: string
  action?: React.ReactNode
  help?: React.ReactNode
}) {
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <div className="min-w-0">
        <h1 className="font-display text-xl font-semibold tracking-tight">{title}</h1>
        {subtitle && (
          <p className="mt-0.5 text-sm" style={{ color: "var(--muted-foreground)" }}>
            {subtitle}
          </p>
        )}
      </div>
      {(action || help) && (
        <div className="flex flex-wrap items-center gap-2 sm:shrink-0 sm:justify-end">
          {action}
          {help}
        </div>
      )}
    </div>
  )
}
