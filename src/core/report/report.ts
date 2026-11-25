import {
  GROUP_KINDS,
  LOCAL_CURRENCY,
  addCents,
  amountOf,
  type Category,
  type Group,
} from '#core/ledger'
import { LINES } from './report.constants.ts'
import { MissingRateError } from './report.errors.ts'
import type { CountedMovement, Line, Report, ReportCatalog, ReportRequest } from './report.types.ts'

type Placed = { category: Category; group: Group; cents: number }

function refuseMissingRates(movements: CountedMovement[], rates: Map<string, number>): void {
  const missing = new Set(
    movements
      .map(({ currency }) => currency)
      .filter((currency) => currency !== LOCAL_CURRENCY && !rates.has(currency)),
  )
  if (missing.size > 0) throw new MissingRateError([...missing].toSorted())
}

function signed(group: Group, cents: number): number {
  return group.kind === 'spending' ? 0 - cents : cents
}

function compare(a: string, b: string): number {
  if (a === b) return 0
  return a < b ? -1 : 1
}

function byPlace(a: Placed, b: Placed): number {
  return (
    GROUP_KINDS.indexOf(a.group.kind) - GROUP_KINDS.indexOf(b.group.kind) ||
    compare(a.group.name, b.group.name) ||
    compare(a.group.id, b.group.id) ||
    compare(a.category.name, b.category.name) ||
    compare(a.category.id, b.category.id)
  )
}

function placed(movements: CountedMovement[], catalog: ReportCatalog): Placed[] {
  const groups = new Map(catalog.groups.map((group) => [group.id, group]))
  const categories = new Map(catalog.categories.map((category) => [category.id, category]))
  const sums = new Map<string, number>()
  for (const { category, cents } of movements)
    sums.set(category, addCents(sums.get(category) ?? 0, cents))
  return [...sums]
    .map(([id, cents]) => {
      const category = categories.get(id)!
      const group = groups.get(category.group)!
      return { category, group, cents: signed(group, cents) }
    })
    .toSorted(byPlace)
}

function groupTotals(rows: Placed[]): { group: Group; cents: number }[] {
  const totals = new Map<string, { group: Group; cents: number }>()
  for (const { group, cents } of rows) {
    const total = totals.get(group.id) ?? { group, cents: 0 }
    totals.set(group.id, { group, cents: addCents(total.cents, cents) })
  }
  return [...totals.values()]
}

function lineTotals(groups: { group: Group; cents: number }[]): Record<Line, number> {
  const sumOf = (kind: Group['kind']) =>
    groups
      .filter(({ group }) => group.kind === kind)
      .reduce((sum, { cents }) => addCents(sum, cents), 0)
  const income = sumOf('income')
  const spending = sumOf('spending')
  return { income, spending, left: addCents(income, 0 - spending), outside: sumOf('outside') }
}

export function reportOf(
  request: ReportRequest,
  movements: CountedMovement[],
  catalog: ReportCatalog,
  rates: Map<string, number>,
): Report {
  refuseMissingRates(movements, rates)
  const rows = placed(movements, catalog)
  const groups = groupTotals(rows)
  const lines = lineTotals(groups)
  return {
    from: request.from,
    to: request.to,
    currency: LOCAL_CURRENCY,
    rates: [],
    totals: LINES.map((line) => ({ line, total: amountOf(lines[line]) })),
    groups: groups.map(({ group, cents }) => ({ ...group, total: amountOf(cents) })),
    categories: rows.map(({ category: { id, group, emoji, name }, cents }) => ({
      id,
      group,
      emoji,
      name,
      total: amountOf(cents),
    })),
  }
}
