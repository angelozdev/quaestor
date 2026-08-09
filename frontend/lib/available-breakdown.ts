import type { MonthAvailable } from "@/lib/api/types"
import { labelOf } from "@/lib/funds"
import { gaveBackLabelOf, metaLabelOf } from "@/lib/metas"

/** One line of the breakdown: what claims the month, and how much. */
export interface BreakdownRow {
  key: string
  label: string
  cents: number
  kind: "income" | "claim"
}

/**
 * Every term of the money available, in the order the owner reads them.
 *
 * `income − Σ claims = free` exactly, so the column a screen renders adds up
 * to the figure above it. Two screens show this list and they must never drift
 * apart on which terms exist or what order they come in, which is why the list
 * is built here and not in either of them.
 *
 * A give-back is a negative claim: a cancelled meta and one whose amount was
 * lowered both hand money back to the month.
 *
 * Every figure here is pesos. A meta held in dollars reports what it asks in
 * dollars and what it costs the month in pesos, and this column is the second
 * one (AC-26).
 */
export function availableRows(available: MonthAvailable): BreakdownRow[] {
  const rows: BreakdownRow[] = [
    { key: "income", label: "Ingreso del mes", cents: available.income, kind: "income" },
    ...available.funds.map((fund) => ({
      key: `fund-${fund.fund_id}`,
      label: labelOf(fund),
      cents: fund.asks,
      kind: "claim" as const,
    })),
    ...available.metas.map((meta) => ({
      key: `meta-${meta.meta_id}`,
      label: metaLabelOf(meta),
      cents: meta.asks_cop,
      kind: "claim" as const,
    })),
  ]
  if (available.contributed !== 0) {
    rows.push({
      key: "contributed",
      label: "Puesto a mano en una meta",
      cents: available.contributed,
      kind: "claim",
    })
  }
  for (const meta of available.metas.filter((it) => it.released > 0)) {
    rows.push({
      key: `back-${meta.meta_id}`,
      label: gaveBackLabelOf(meta),
      cents: -meta.released,
      kind: "claim",
    })
  }
  rows.push({
    key: "uncovered",
    label: "Sin fondo que lo cubra",
    cents: available.uncovered,
    kind: "claim",
  })
  return rows
}
