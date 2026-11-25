import { sql } from 'drizzle-orm'
import { check, integer, sqliteTable, text } from 'drizzle-orm/sqlite-core'

export const rates = sqliteTable(
  'rates',
  {
    currency: text().primaryKey(),
    rate: integer().notNull(),
    createdAt: text('created_at').notNull(),
    updatedAt: text('updated_at').notNull(),
  },
  (table) => [
    check(
      'rates_currency',
      sql`length(${table.currency}) = 3 AND ${table.currency} NOT GLOB '*[^A-Z]*' AND ${table.currency} <> 'COP'`,
    ),
    check('rates_rate', sql`${table.rate} > 0`),
  ],
)
