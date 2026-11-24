import {
  CENTS_PER_UNIT,
  CURRENCIES,
  DECIMAL_DIGITS,
  ID_ALPHABET,
  ID_LENGTH,
} from './ledger.constants.ts'
import type { RandomIndex } from './ledger.types.ts'

export function drawCode(randomIndex: RandomIndex): string {
  return Array.from({ length: ID_LENGTH }, () =>
    ID_ALPHABET.charAt(randomIndex(ID_ALPHABET.length)),
  ).join('')
}

export function isCurrency(code: string): boolean {
  return CURRENCIES.has(code)
}

export function centsOf(text: string): number {
  const [whole = '', decimals = ''] = text.replace('-', '').split('.')
  const cents = Number(whole) * CENTS_PER_UNIT + Number(decimals.padEnd(DECIMAL_DIGITS, '0'))
  return text.startsWith('-') ? 0 - cents : cents
}

export function amountOf(cents: number): number {
  return cents / CENTS_PER_UNIT
}
