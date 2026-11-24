import type { BOOKED_ACCOUNTS, FAULTS, MOVED_ACCOUNTS } from './arbitraries.constants.ts'

export type BookedAccount = (typeof BOOKED_ACCOUNTS)[number]

export type Booked = { account: BookedAccount; cents: number; date: string }

export type Fault = (typeof FAULTS)[number]

export type MovedAccount = (typeof MOVED_ACCOUNTS)[number]

export type Moved = {
  from: MovedAccount
  to: MovedAccount
  sent: number
  received: number
  date: string
}
