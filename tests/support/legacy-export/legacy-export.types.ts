import type { LegacyExport } from '#core/legacy'
import type { TABLE_NAMES } from './legacy-export.constants.ts'

export type TableName = (typeof TABLE_NAMES)[number]

export type ExportTransaction = LegacyExport['transactions'][number]

export type ExportRows = {
  accounts: (LegacyExport['accounts'][number] & { balance: number })[]
  categories: LegacyExport['categories']
  tags: LegacyExport['tags']
  transactions: ExportTransaction[]
  tagLinks: LegacyExport['tagLinks']
}

type ManifestOverride = { rows?: number; sha256?: string }

export type ExportOptions = {
  manifest?: Partial<Record<TableName, ManifestOverride>>
  extraLines?: Partial<Record<TableName, string[]>>
}
