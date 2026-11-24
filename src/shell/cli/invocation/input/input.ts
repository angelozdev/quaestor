import type { z } from 'zod'
import { PATH_SEPARATOR } from './input.constants.ts'
import { InvalidInputError } from './input.errors.ts'

function pathPart(part: PropertyKey, index: number): string {
  if (typeof part === 'number') return `[${part}]`
  return index === 0 ? String(part) : `${PATH_SEPARATOR}${String(part)}`
}

function issueLines({ path, message, ...issue }: z.core.$ZodIssue): string[] {
  const paths =
    issue.code === 'unrecognized_keys' ? issue.keys.map((key) => [...path, key]) : [path]
  return paths.map((where) =>
    where.length === 0 ? message : `${where.map(pathPart).join('')}: ${message}`,
  )
}

export function parsed<T>(schema: z.ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value)
  if (result.success) return result.data
  throw new InvalidInputError(result.error.issues.flatMap(issueLines))
}
