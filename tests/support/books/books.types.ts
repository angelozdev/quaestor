import type { LedgerCli } from '../ledger/ledger.types.ts'

export type Json = Record<string, unknown>

export type Books = {
  cli: LedgerCli
  wallet: string
  savings: string
  bank: string
  food: string
}

export type Spender = Pick<Books, 'wallet' | 'food'>

export type Mover = Pick<Books, 'wallet' | 'savings'>

export type Transfer = { from: Json; to: Json }
