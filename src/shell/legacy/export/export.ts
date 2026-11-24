import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import type { z } from 'zod'
import type { LegacyExport } from '#core/legacy'
import {
  HEX,
  LINE_BREAK,
  MANIFEST_FILE,
  NOT_JSON,
  PATH_SEPARATOR,
  SHA256,
  SHA256_DIFFERS,
} from './export.constants.ts'
import { ExportMismatchError } from './export.errors.ts'
import {
  accountSchema,
  categorySchema,
  manifestSchema,
  tagLinkSchema,
  tagSchema,
  transactionSchema,
} from './export.schema.ts'

type Table = z.infer<typeof manifestSchema>['tables'][number]

function linesOf(text: string): string[] {
  const lines = text.split(LINE_BREAK)
  if (lines.at(-1) === '') lines.pop()
  return lines
}

async function checkedLines(folder: string, { file, rows, sha256 }: Table): Promise<string[]> {
  const bytes = await readFile(join(folder, file))
  if (createHash(SHA256).update(bytes).digest(HEX) !== sha256)
    throw new ExportMismatchError(file, SHA256_DIFFERS)
  const lines = linesOf(bytes.toString())
  if (lines.length !== rows)
    throw new ExportMismatchError(file, `has ${lines.length} rows, manifest.json says ${rows}`)
  return lines
}

function issueText({ path, message }: z.core.$ZodIssue): string {
  return path.length === 0 ? message : `${path.join(PATH_SEPARATOR)}: ${message}`
}

function parsedLine<T>(file: string, line: string, number: number, schema: z.ZodType<T>): T {
  const reject = (issue: string) => new ExportMismatchError(file, `line ${number}: ${issue}`)
  let value: unknown
  try {
    value = JSON.parse(line)
  } catch {
    throw reject(NOT_JSON)
  }
  const result = schema.safeParse(value)
  if (!result.success) throw reject(issueText(result.error.issues[0]))
  return result.data
}

export async function readLegacyExport(folder: string): Promise<LegacyExport> {
  const manifest = manifestSchema.parse(
    JSON.parse(await readFile(join(folder, MANIFEST_FILE), 'utf8')),
  )
  const tables = new Map(manifest.tables.map((table) => [table.name, table]))
  const checked = new Map<string, string[]>()
  for (const table of manifest.tables) checked.set(table.name, await checkedLines(folder, table))
  const rowsOf = <T>(name: string, schema: z.ZodType<T>): T[] =>
    checked
      .get(name)!
      .map((line, index) => parsedLine(tables.get(name)!.file, line, index + 1, schema))
  return {
    exportedAt: manifest.exportedAt,
    balances: new Map(manifest.accounts.map(({ id, balance }) => [id, balance])),
    accounts: rowsOf('account', accountSchema),
    categories: rowsOf('category', categorySchema),
    tags: rowsOf('tag', tagSchema),
    transactions: rowsOf('transaction', transactionSchema),
    tagLinks: rowsOf('transaction_tag', tagLinkSchema),
  }
}
