import type { ACCOUNT_TYPES } from './ledger.constants.ts'

export type AccountType = (typeof ACCOUNT_TYPES)[number]

export type RandomIndex = (bound: number) => number

export type WriteDeps = { randomIndex: RandomIndex; now: Date }

export type AccountDraft = {
  emoji: string
  name: string
  type: AccountType
  currency: string
  openingAmount: number
  openingDate: string
}

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

export type CategoryDraft = { emoji: string; name: string }

export type Category = {
  id: string
  emoji: string | null
  name: string
  archived: boolean
}
