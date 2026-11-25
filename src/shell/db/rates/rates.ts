import { eq } from 'drizzle-orm'
import { amountOf } from '#core/ledger'
import { database } from '../database/database.ts'
import type { Store } from '../database/database.types.ts'
import { rates } from './rates.schema.ts'
import type { RateChange } from './rates.types.ts'

export function setRate(store: Store, currency: string, rate: number, now: Date): RateChange {
  const instant = now.toISOString()
  const db = database(store)
  const before = db
    .select({ rate: rates.rate })
    .from(rates)
    .where(eq(rates.currency, currency))
    .get()
  db.insert(rates)
    .values({ currency, rate, createdAt: instant, updatedAt: instant })
    .onConflictDoUpdate({ target: rates.currency, set: { rate, updatedAt: instant } })
    .run()
  return {
    currency,
    before: before === undefined ? null : amountOf(before.rate),
    after: amountOf(rate),
  }
}
