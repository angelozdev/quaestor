import type { Category, Group } from '#core/ledger'
import type { LINES } from './report.constants.ts'

export type CountedMovement = { date: string; cents: number; currency: string; category: string }

export type ReportRequest = { from: string; to: string; byMonth: boolean }

export type Section = { month: string | null; movements: CountedMovement[] }

export type ReportCatalog = { groups: Group[]; categories: Category[] }

export type Line = (typeof LINES)[number]

export type Columns = { total: number; [currency: string]: unknown }

export type Tables = {
  totals: ({ line: Line } & Columns)[]
  groups: (Group & Columns)[]
  categories: ({ id: string; group: string; emoji: string | null; name: string } & Columns)[]
}

export type Report = {
  from: string
  to: string
  currency: string
  rates: { currency: string; rate: number }[]
} & Tables
