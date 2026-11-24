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

export type BalanceChange = { account: string; currency: string; before: number; after: number }

export type WriteResult = {
  deleted: MovementRow[]
  recorded: MovementRow[]
  balances: BalanceChange[]
}
