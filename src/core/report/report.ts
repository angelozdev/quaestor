import {
  GROUP_KINDS,
  LOCAL_CURRENCY,
  addCents,
  amountOf,
  convertCents,
  type Category,
  type Group,
} from '#core/ledger'
import { LINES } from './report.constants.ts'
import { MissingRateError } from './report.errors.ts'
import type {
  Columns,
  CountedMovement,
  Line,
  Report,
  ReportCatalog,
  ReportRequest,
} from './report.types.ts'

type Figures = number[]

type Placed = { category: Category; group: Group; figures: Figures }

type GroupFigures = { group: Group; figures: Figures }

function foreignCurrencies(movements: CountedMovement[]): string[] {
  const currencies = movements
    .map(({ currency }) => currency)
    .filter((currency) => currency !== LOCAL_CURRENCY)
  return [...new Set(currencies)].toSorted()
}

function refuseMissingRates(currencies: string[], rates: Map<string, number>): void {
  const missing = currencies.filter((currency) => !rates.has(currency))
  if (missing.length > 0) throw new MissingRateError(missing)
}

function plus(a: Figures, b: Figures): Figures {
  return a.map((cents, index) => addCents(cents, b[index]!))
}

function figuresOf(
  { cents, currency }: CountedMovement,
  currencies: string[],
  rates: Map<string, number>,
): Figures {
  const converted = currency === LOCAL_CURRENCY ? cents : convertCents(cents, rates.get(currency)!)
  return [converted, ...currencies.map((foreign) => (foreign === currency ? cents : 0))]
}

function signed(group: Group, figures: Figures): Figures {
  return group.kind === 'spending' ? figures.map((cents) => 0 - cents) : figures
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

function placed(
  movements: CountedMovement[],
  catalog: ReportCatalog,
  currencies: string[],
  rates: Map<string, number>,
): Placed[] {
  const groups = new Map(catalog.groups.map((group) => [group.id, group]))
  const categories = new Map(catalog.categories.map((category) => [category.id, category]))
  const sums = new Map<string, Figures>()
  for (const movement of movements) {
    const figures = figuresOf(movement, currencies, rates)
    const sum = sums.get(movement.category)
    sums.set(movement.category, sum === undefined ? figures : plus(sum, figures))
  }
  return [...sums]
    .map(([id, figures]) => {
      const category = categories.get(id)!
      const group = groups.get(category.group)!
      return { category, group, figures: signed(group, figures) }
    })
    .toSorted(byPlace)
}

function groupFigures(rows: Placed[]): GroupFigures[] {
  const totals = new Map<string, GroupFigures>()
  for (const { group, figures } of rows) {
    const total = totals.get(group.id)
    totals.set(group.id, {
      group,
      figures: total === undefined ? figures : plus(total.figures, figures),
    })
  }
  return [...totals.values()]
}

function lineFigures(groups: GroupFigures[], width: number): Record<Line, Figures> {
  const zero = Array.from({ length: width }, () => 0)
  const sumOf = (kind: Group['kind']) =>
    groups
      .filter(({ group }) => group.kind === kind)
      .reduce((sum, { figures }) => plus(sum, figures), zero)
  const income = sumOf('income')
  const spending = sumOf('spending')
  return {
    income,
    spending,
    left: plus(
      income,
      spending.map((cents) => 0 - cents),
    ),
    outside: sumOf('outside'),
  }
}

function columnsOf(figures: Figures, currencies: string[]): Columns {
  const [total = 0, ...parts] = figures.map(amountOf)
  return {
    total,
    ...Object.fromEntries(currencies.map((currency, index) => [currency, parts[index]!])),
  }
}

export function reportOf(
  request: ReportRequest,
  movements: CountedMovement[],
  catalog: ReportCatalog,
  rates: Map<string, number>,
): Report {
  const currencies = foreignCurrencies(movements)
  refuseMissingRates(currencies, rates)
  const rows = placed(movements, catalog, currencies, rates)
  const groups = groupFigures(rows)
  const lines = lineFigures(groups, currencies.length + 1)
  return {
    from: request.from,
    to: request.to,
    currency: LOCAL_CURRENCY,
    rates: currencies.map((currency) => ({ currency, rate: amountOf(rates.get(currency)!) })),
    totals: LINES.map((line) => ({ line, ...columnsOf(lines[line], currencies) })),
    groups: groups.map(({ group, figures }) => ({ ...group, ...columnsOf(figures, currencies) })),
    categories: rows.map(({ category: { id, group, emoji, name }, figures }) => ({
      id,
      group,
      emoji,
      name,
      ...columnsOf(figures, currencies),
    })),
  }
}
