import type { LedgerCli } from '../ledger/ledger.types.ts'
import type { REPORT_CATEGORIES } from './reports.constants.ts'

export type ReportBooks = {
  cli: LedgerCli
  bank: string
  savings: string
  wallet: string
  card: string
  salary: string
  restaurants: string
  clothing: string
  investment: string
}

type Line = { line: string; total: number; [column: string]: unknown }

type GroupRow = {
  id: string
  kind: string
  emoji: string
  name: string
  total: number
  [column: string]: unknown
}

type CategoryRow = {
  id: string
  group: string
  emoji: string
  name: string
  total: number
  [column: string]: unknown
}

export type Report = {
  from: string
  to: string
  currency: string
  rates: { currency: string; rate: number }[]
  totals: Line[]
  groups: GroupRow[]
  categories: CategoryRow[]
}

export type MixedMove = {
  usd: boolean
  cents: number
  category: (typeof REPORT_CATEGORIES)[number]
  month: number
  day: number
}
