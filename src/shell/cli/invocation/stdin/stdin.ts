import { text } from 'node:stream/consumers'
import type { CliContext } from '../../main/main.types.ts'
import { InvalidJsonError } from './stdin.errors.ts'

export function processStdin(): Promise<string> {
  return text(process.stdin)
}

export async function readJson(context: CliContext): Promise<unknown> {
  try {
    return JSON.parse(await context.stdin())
  } catch (error) {
    if (error instanceof SyntaxError) throw new InvalidJsonError(error.message)
    throw error
  }
}
