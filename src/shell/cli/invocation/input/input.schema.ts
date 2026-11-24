import { z } from 'zod'
import { AMOUNT_PATTERN, TAG_PATTERN, centsOf, isCurrency } from '#core/ledger'
import {
  AMOUNT_MESSAGE,
  AMOUNT_TOO_LARGE_MESSAGE,
  CURRENCY_MESSAGE,
  DATE_MESSAGE,
  EMOJI_MESSAGE,
  EMOJI_PATTERN,
  REQUIRED_MESSAGE,
  TAG_MESSAGE,
  UNKNOWN_KEY_MESSAGE,
} from './input.constants.ts'

function wrongOr(message: string) {
  return {
    error: (issue: { input?: unknown }) => (issue.input === undefined ? REQUIRED_MESSAGE : message),
  }
}

function listOf(values: readonly string[]): string {
  return `${values.slice(0, -1).join(', ')} or ${values.at(-1)}`
}

export const requiredText = z.string(wrongOr(REQUIRED_MESSAGE)).trim().min(1, REQUIRED_MESSAGE)

export const dateText = z.iso.date(wrongOr(DATE_MESSAGE))

export const amountText = z
  .string(wrongOr(AMOUNT_MESSAGE))
  .regex(AMOUNT_PATTERN, AMOUNT_MESSAGE)
  .transform(centsOf)
  .refine(Number.isSafeInteger, { error: AMOUNT_TOO_LARGE_MESSAGE, abort: true })

export const currencyCode = z.string(wrongOr(CURRENCY_MESSAGE)).refine(isCurrency, CURRENCY_MESSAGE)

export const emojiText = z.string(wrongOr(EMOJI_MESSAGE)).regex(EMOJI_PATTERN, EMOJI_MESSAGE)

export const tagText = z.string(wrongOr(TAG_MESSAGE)).regex(TAG_PATTERN, TAG_MESSAGE)

export const dryRun = z.boolean().default(false)

export function oneOf<const T extends readonly [string, ...string[]]>(values: T) {
  return z.enum(values, wrongOr(`must be one of ${listOf(values)}`))
}

export function fields<T extends z.core.$ZodShape>(shape: T) {
  return z.strictObject(shape, {
    error: (issue) => (issue.code === 'unrecognized_keys' ? UNKNOWN_KEY_MESSAGE : undefined),
  })
}
