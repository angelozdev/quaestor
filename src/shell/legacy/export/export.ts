import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import type { z } from 'zod'
import type { LegacyExport } from '#core/legacy'
import {
  CANNOT_READ,
  HEX,
  LINE_BREAK,
  MANIFEST_FILE,
  NOT_JSON,
  PATH_SEPARATOR,
  SHA256,
  SHA256_DIFFERS,
  USED_TABLES,
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

function causeOf(error: unknown): string {
  return error instanceof Error && 'code' in error ? String(error.code) : String(error)
}

async function bytesOf(folder: string, file: string): Promise<Buffer> {
  try {
    return await readFile(join(folder, file))
  } catch (error) {
    throw new ExportMismatchError(file, `${CANNOT_READ}${causeOf(error)}`)
  }
}

function linesOf(text: string): string[] {
  const lines = text.split(LINE_BREAK)
  if (lines.at(-1) === '') lines.pop()
  return lines
}

async function checkedLines(folder: string, { file, rows, sha256 }: Table): Promise<string[]> {
  const bytes = await bytesOf(folder, file)
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

function parsedJson<T>(
  text: string,
  schema: z.ZodType<T>,
  reject: (issue: string) => ExportMismatchError,
): T {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch {
    throw reject(NOT_JSON)
  }
  const result = schema.safeParse(value)
  if (!result.success) throw reject(issueText(result.error.issues[0]))
  return result.data
}

async function readManifest(folder: string) {
  const manifest = parsedJson(
    (await bytesOf(folder, MANIFEST_FILE)).toString(),
    manifestSchema,
    (issue) => new ExportMismatchError(MANIFEST_FILE, issue),
  )
  for (const name of USED_TABLES)
    if (!manifest.tables.some((table) => table.name === name))
      throw new ExportMismatchError(MANIFEST_FILE, `lists no ${name} table`)
  return manifest
}

export async function readLegacyExport(folder: string): Promise<LegacyExport> {
  const manifest = await readManifest(folder)
  const checked = new Map<string, { file: string; lines: string[] }>()
  for (const table of manifest.tables)
    checked.set(table.name, { file: table.file, lines: await checkedLines(folder, table) })
  const rowsOf = <T>(name: (typeof USED_TABLES)[number], schema: z.ZodType<T>): T[] => {
    const { file, lines } = checked.get(name)!
    return lines.map((line, index) =>
      parsedJson(
        line,
        schema,
        (issue) => new ExportMismatchError(file, `line ${index + 1}: ${issue}`),
      ),
    )
  }
  const balances = new Map(manifest.accounts.map(({ id, balance }) => [id, balance]))
  const accounts = rowsOf('account', accountSchema)
  const unbalanced = accounts.find(({ id }) => !balances.has(id))
  if (unbalanced !== undefined)
    throw new ExportMismatchError(MANIFEST_FILE, `account ${unbalanced.id} has no balance`)
  return {
    exportedAt: manifest.exportedAt,
    balances,
    accounts,
    categories: rowsOf('category', categorySchema),
    tags: rowsOf('tag', tagSchema),
    transactions: rowsOf('transaction', transactionSchema),
    tagLinks: rowsOf('transaction_tag', tagLinkSchema),
  }
}
