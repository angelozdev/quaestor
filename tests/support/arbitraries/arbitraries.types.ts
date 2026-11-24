import type { BOOKED_ACCOUNTS, FAULTS } from './arbitraries.constants.ts'

export type BookedAccount = (typeof BOOKED_ACCOUNTS)[number]

export type Booked = { account: BookedAccount; cents: number; date: string }

export type Fault = (typeof FAULTS)[number]
