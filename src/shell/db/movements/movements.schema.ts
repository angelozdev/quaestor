import { sql } from 'drizzle-orm'
import { check, index, integer, primaryKey, sqliteTable, text } from 'drizzle-orm/sqlite-core'
import { accounts } from '../accounts/accounts.schema.ts'
import { categories } from '../categories/categories.schema.ts'
import { tags } from '../tags/tags.schema.ts'

export const movements = sqliteTable(
  'movements',
  {
    seq: integer().primaryKey(),
    id: text().notNull().unique(),
    accountId: text('account_id')
      .notNull()
      .references(() => accounts.id),
    date: text().notNull(),
    payee: text().notNull(),
    amount: integer().notNull(),
    categoryId: text('category_id').references(() => categories.id),
    transfer: text(),
    note: text(),
    createdAt: text('created_at').notNull(),
    updatedAt: text('updated_at').notNull(),
    deletedAt: text('deleted_at'),
  },
  (table) => [
    check(
      'movements_id',
      sql`${table.id} IS NOT NULL AND length(${table.id}) = 4 AND ${table.id} NOT GLOB '*[^0-9a-hjkmnp-tv-z]*'`,
    ),
    check('movements_date', sql`date(${table.date}) IS ${table.date}`),
    check('movements_payee', sql`length(trim(${table.payee})) > 0`),
    check('movements_amount', sql`${table.amount} <> 0`),
    check(
      'movements_category_or_transfer',
      sql`(${table.categoryId} IS NULL) = (${table.transfer} IS NOT NULL)`,
    ),
    index('movements_account_date').on(table.accountId, table.date, table.seq),
  ],
)

export const movementTags = sqliteTable(
  'movement_tags',
  {
    movementId: text('movement_id')
      .notNull()
      .references(() => movements.id),
    tag: text()
      .notNull()
      .references(() => tags.name),
  },
  (table) => [primaryKey({ columns: [table.movementId, table.tag] })],
)
