import type { LedgerCli } from '../ledger/ledger.types.ts'

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

type Line = { line: string; total: number }

type GroupRow = { id: string; kind: string; emoji: string; name: string; total: number }

type CategoryRow = { id: string; group: string; emoji: string; name: string; total: number }

export type Report = {
  from: string
  to: string
  currency: string
  rates: { currency: string; rate: number }[]
  totals: Line[]
  groups: GroupRow[]
  categories: CategoryRow[]
}
