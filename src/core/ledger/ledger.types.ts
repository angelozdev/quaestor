import type { ACCOUNT_TYPES } from './ledger.constants.ts'

export type AccountType = (typeof ACCOUNT_TYPES)[number]

type Account = {
  id: string
  emoji: string | null
  name: string
  type: AccountType
  currency: string
  archived: boolean
  openingAmount: number
  openingDate: string | null
}

export type AccountRow = Account & { balance: number }
