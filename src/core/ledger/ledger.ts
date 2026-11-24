import {
  CENTS_PER_UNIT,
  CURRENCIES,
  DECIMAL_DIGITS,
  ID_ALPHABET,
  ID_LENGTH,
  PROBLEM_CODES,
} from './ledger.constants.ts'
import type {
  Account,
  Catalog,
  MovementDraft,
  RandomIndex,
  WriteProblem,
  WriteRequest,
} from './ledger.types.ts'

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

function notFound(item: string, kind: string, id: string): WriteProblem {
  return { code: PROBLEM_CODES.NotFound, item, message: `${kind} ${id} does not exist` }
}

function accountProblems(account: Account, movement: MovementDraft, item: string): WriteProblem[] {
  const problems: WriteProblem[] = []
  if (account.openingDate !== null && movement.date < account.openingDate)
    problems.push({
      code: PROBLEM_CODES.BeforeOpening,
      item,
      message: `account ${account.id} opens on ${account.openingDate}, after ${movement.date}`,
    })
  if (movement.currency !== account.currency)
    problems.push({
      code: PROBLEM_CODES.CurrencyMismatch,
      item,
      message: `account ${account.id} holds ${account.currency}, not ${movement.currency}`,
    })
  return problems
}

function movementProblems(
  movement: MovementDraft,
  item: string,
  { accounts, categories, tags }: Catalog,
): WriteProblem[] {
  const account = accounts.get(movement.account)
  return [
    ...(account === undefined
      ? [notFound(item, 'account', movement.account)]
      : accountProblems(account, movement, item)),
    ...(categories.has(movement.category) ? [] : [notFound(item, 'category', movement.category)]),
    ...movement.tags.filter((tag) => !tags.has(tag)).map((tag) => notFound(item, 'tag', tag)),
  ]
}

export function checkWrite(request: WriteRequest, catalog: Catalog): WriteProblem[] {
  return request.movements.flatMap((movement, index) =>
    movementProblems(movement, `movements[${index}]`, catalog),
  )
}
