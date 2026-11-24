import type { z } from 'zod'
import { PATH_SEPARATOR } from './input.constants.ts'
import { InvalidInputError } from './input.errors.ts'

function issueLines({ path, message, ...issue }: z.core.$ZodIssue): string[] {
  const paths =
    issue.code === 'unrecognized_keys' ? issue.keys.map((key) => [...path, key]) : [path]
  return paths.map((where) => `${where.join(PATH_SEPARATOR)}: ${message}`)
}

export function parsed<T>(schema: z.ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value)
  if (result.success) return result.data
  throw new InvalidInputError(result.error.issues.flatMap(issueLines))
}
