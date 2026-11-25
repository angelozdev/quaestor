export type MovementRow = {
  id: string
  date: string
  account: string
  payee: string
  amount: number
  currency: string
  category: string | null
  tags: string
  note: string | null
  transfer: string | null
}

export type ListedMovement = MovementRow & { balance: number }

export type MovementFilter = { account?: string; from?: string; to?: string; payee?: string }

export type CountedFilter = {
  from: string
  to: string
  tag?: string
  withoutTag?: string
  payee?: string
}

export type BalanceChange = { account: string; currency: string; before: number; after: number }

export type WriteResult = {
  deleted: MovementRow[]
  recorded: MovementRow[]
  balances: BalanceChange[]
}
