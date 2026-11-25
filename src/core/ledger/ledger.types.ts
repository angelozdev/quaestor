import type { ACCOUNT_TYPES, GROUP_KINDS } from './ledger.constants.ts'

export type AccountType = (typeof ACCOUNT_TYPES)[number]

export type GroupKind = (typeof GROUP_KINDS)[number]

export type Group = { id: string; kind: GroupKind; emoji: string; name: string }

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

export type Account = {
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

export type CategoryDraft = { emoji: string; name: string; group: string }

export type Category = {
  id: string
  group: string
  emoji: string | null
  name: string
  archived: boolean
}

export type MovementDraft = {
  account: string
  date: string
  payee: string
  amount: number
  currency: string
  category: string
  tags: string[]
  note: string | null
}

export type HalfDraft = Omit<MovementDraft, 'category'>

export type TransferDraft = { from: HalfDraft; to: HalfDraft }

export type WriteRequest = {
  delete: string[]
  movements: MovementDraft[]
  transfers: TransferDraft[]
}

export type Catalog = {
  accounts: Map<string, Account>
  categories: Map<string, Category>
  tags: Set<string>
  movements: Set<string>
}

export type WriteProblem = { code: string; item: string; message: string }
