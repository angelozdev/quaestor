import { createHash } from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { tempDir } from '../temp-dir/temp-dir.ts'
import {
  EXPORTED_AT,
  FIXTURE_ROWS,
  MANIFEST_DUMP,
  MANIFEST_FORMAT,
  MANIFEST_SOURCE,
  TABLE_NAMES,
  UNPARSED_TABLES,
} from './legacy-export.constants.ts'
import type {
  ExportOptions,
  ExportRows,
  ExportTransaction,
  Manifest,
  TableName,
} from './legacy-export.types.ts'

type Row = Record<string, string | null>

function textOf(value: string | number | boolean | null): string | null {
  return value === null ? null : String(value)
}

function rowOf(columns: Record<string, string | number | boolean | null>): Row {
  return Object.fromEntries(Object.entries(columns).map(([name, value]) => [name, textOf(value)]))
}

function transactionRow(transaction: ExportTransaction, currency: string): Row {
  return rowOf({
    id: transaction.id,
    date: transaction.date,
    payee: transaction.payee,
    notes: transaction.notes,
    type: transaction.type,
    status: transaction.status,
    amount: transaction.amount,
    currency,
    account_id: transaction.accountId,
    category_id: transaction.categoryId,
    recurring_id: null,
    transfer_group_id: transaction.transferGroup,
    source: 'manual',
    created_at: transaction.createdAt,
    transfer_direction: transaction.direction,
    meta_id: null,
  })
}

function tableRows(rows: ExportRows): Partial<Record<TableName, Row[]>> {
  const currencies = new Map(rows.accounts.map(({ id, currency }) => [id, currency]))
  return {
    ...Object.fromEntries(
      Object.entries(UNPARSED_TABLES).map(([name, table]) => [name, table.map(rowOf)]),
    ),
    account: rows.accounts.map(rowOf),
    category: rows.categories.map(({ id, name, archived }) =>
      rowOf({
        id,
        name,
        group_id: '1',
        is_income: false,
        exclude_from_budget: false,
        exclude_from_totals: false,
        archived,
        counts_as_saving: false,
      }),
    ),
    tag: rows.tags.map(rowOf),
    transaction: rows.transactions.map((transaction) =>
      transactionRow(transaction, currencies.get(transaction.accountId) ?? ''),
    ),
    transaction_tag: rows.tagLinks.map(({ transactionId, tagId }) =>
      rowOf({ transaction_id: transactionId, tag_id: tagId }),
    ),
  }
}

export function writeLegacyExport(rows: ExportRows, options: ExportOptions = {}): string {
  const folder = tempDir('quaestor-legacy-')
  mkdirSync(join(folder, 'tables'))
  const contents = tableRows(rows)
  const tables = TABLE_NAMES.map((name) => {
    const file = `tables/${name}.jsonl`
    const lines = [
      ...(contents[name] ?? []).map((row) => JSON.stringify(row)),
      ...(options.extraLines?.[name] ?? []),
    ]
    const text = lines.map((line) => `${line}\n`).join('')
    writeFileSync(join(folder, file), text)
    const sha256 = createHash('sha256').update(text).digest('hex')
    return { name, file, rows: lines.length, sha256, ...options.manifest?.[name] }
  })
  const manifest = {
    exportedAt: EXPORTED_AT,
    source: MANIFEST_SOURCE,
    format: MANIFEST_FORMAT,
    dump: MANIFEST_DUMP,
    tables,
    accounts: rows.accounts.map(({ id, name, currency, balance }) =>
      rowOf({ id, name, currency, balance }),
    ),
  }
  writeFileSync(join(folder, 'manifest.json'), JSON.stringify(manifest, null, 2))
  return folder
}

export function rewriteManifest(folder: string, change: (manifest: Manifest) => unknown): void {
  const path = join(folder, 'manifest.json')
  const manifest = JSON.parse(readFileSync(path, 'utf8')) as Manifest
  change(manifest)
  writeFileSync(path, JSON.stringify(manifest, null, 2))
}

export function fixtureExport(options: ExportOptions = {}): string {
  return writeLegacyExport(FIXTURE_ROWS, options)
}
