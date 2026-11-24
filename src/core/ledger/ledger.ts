import {
  CENTS_PER_UNIT,
  CURRENCIES,
  DECIMAL_DIGITS,
  DIACRITICS,
  ID_ALPHABET,
  ID_LENGTH,
  PROBLEM_CODES,
} from './ledger.constants.ts'
import type {
  Account,
  Catalog,
  HalfDraft,
  MovementDraft,
  RandomIndex,
  TransferDraft,
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

function plain(text: string): string {
  return text.normalize('NFD').replace(DIACRITICS, '').toLowerCase()
}

export function matchesPayee(payee: string, text: string): boolean {
  return plain(payee).includes(plain(text))
}

function notFound(item: string, kind: string, id: string): WriteProblem {
  return { code: PROBLEM_CODES.NotFound, item, message: `${kind} ${id} does not exist` }
}

function archived(item: string, kind: string, id: string): WriteProblem {
  return { code: PROBLEM_CODES.Archived, item, message: `${kind} ${id} is archived` }
}

function accountProblems(account: Account, movement: HalfDraft, item: string): WriteProblem[] {
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

function accountChecks(
  half: HalfDraft,
  item: string,
  accounts: Catalog['accounts'],
): WriteProblem[] {
  const account = accounts.get(half.account)
  if (account === undefined) return [notFound(item, 'account', half.account)]
  return account.archived
    ? [archived(item, 'account', account.id)]
    : accountProblems(account, half, item)
}

function categoryChecks(
  id: string,
  item: string,
  categories: Catalog['categories'],
): WriteProblem[] {
  const category = categories.get(id)
  if (category === undefined) return [notFound(item, 'category', id)]
  return category.archived ? [archived(item, 'category', category.id)] : []
}

function tagChecks(half: HalfDraft, item: string, tags: Catalog['tags']): WriteProblem[] {
  return half.tags.filter((tag) => !tags.has(tag)).map((tag) => notFound(item, 'tag', tag))
}

function movementProblems(
  movement: MovementDraft,
  item: string,
  { accounts, categories, tags }: Catalog,
): WriteProblem[] {
  return [
    ...accountChecks(movement, item, accounts),
    ...categoryChecks(movement.category, item, categories),
    ...tagChecks(movement, item, tags),
  ]
}

function halfProblems(half: HalfDraft, item: string, { accounts, tags }: Catalog): WriteProblem[] {
  return [...accountChecks(half, item, accounts), ...tagChecks(half, item, tags)]
}

function transferProblems(
  { from, to }: TransferDraft,
  item: string,
  catalog: Catalog,
): WriteProblem[] {
  return [
    ...(from.account === to.account
      ? [
          {
            code: PROBLEM_CODES.SameAccountTransfer,
            item,
            message: `a transfer needs two different accounts, not ${from.account} twice`,
          },
        ]
      : []),
    ...halfProblems(from, `${item}.from`, catalog),
    ...halfProblems(to, `${item}.to`, catalog),
  ]
}

export function checkWrite(request: WriteRequest, catalog: Catalog): WriteProblem[] {
  return [
    ...request.delete.flatMap((id, index) =>
      catalog.movements.has(id) ? [] : [notFound(`delete[${index}]`, 'movement', id)],
    ),
    ...request.movements.flatMap((movement, index) =>
      movementProblems(movement, `movements[${index}]`, catalog),
    ),
    ...request.transfers.flatMap((transfer, index) =>
      transferProblems(transfer, `transfers[${index}]`, catalog),
    ),
  ]
}
