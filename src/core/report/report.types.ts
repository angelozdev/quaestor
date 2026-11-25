import type { Category, Group } from '#core/ledger'
import type { LINES } from './report.constants.ts'

export type CountedMovement = { date: string; cents: number; currency: string; category: string }

export type ReportRequest = { from: string; to: string }

export type ReportCatalog = { groups: Group[]; categories: Category[] }

export type Line = (typeof LINES)[number]

export type Report = {
  from: string
  to: string
  currency: string
  rates: { currency: string; rate: number }[]
  totals: { line: Line; total: number }[]
  groups: (Group & { total: number })[]
  categories: { id: string; group: string; emoji: string | null; name: string; total: number }[]
}
