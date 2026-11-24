import type { Account, AccountType, Category } from '#core/ledger'

export type LegacyTransaction = {
  id: number
  date: string
  payee: string
  notes: string | null
  type: 'expense' | 'income' | 'transfer'
  status: 'posted' | 'skipped' | 'planned'
  amount: number
  accountId: number
  categoryId: number | null
  transferGroup: string | null
  direction: 'out' | 'in_' | null
  createdAt: string
}

export type LegacyExport = {
  exportedAt: string
  balances: Map<number, number>
  accounts: {
    id: number
    name: string
    type: AccountType
    currency: string
    archived: boolean
  }[]
  categories: { id: number; name: string; archived: boolean }[]
  tags: { id: number; name: string }[]
  transactions: LegacyTransaction[]
  tagLinks: { transactionId: number; tagId: number }[]
}

export type StoredMovement = {
  id: string
  account: string
  date: string
  payee: string
  amount: number
  category: string | null
  transfer: string | null
  note: string | null
  createdAt: string
}

export type Ledger = {
  accounts: Account[]
  categories: Category[]
  tags: string[]
  movements: StoredMovement[]
  tagLinks: { movement: number; tag: string }[]
}
