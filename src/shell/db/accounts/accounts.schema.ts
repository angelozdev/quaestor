import { sql } from 'drizzle-orm'
import { check, integer, sqliteTable, text, uniqueIndex } from 'drizzle-orm/sqlite-core'
import { ACCOUNT_TYPES, type AccountType } from '#core/ledger'

export const accounts = sqliteTable(
  'accounts',
  {
    id: text().primaryKey(),
    emoji: text(),
    name: text().notNull(),
    type: text().$type<AccountType>().notNull(),
    currency: text().notNull(),
    archived: integer({ mode: 'boolean' }).notNull().default(false),
    openingAmount: integer('opening_amount').notNull().default(0),
    openingDate: text('opening_date'),
    createdAt: text('created_at').notNull(),
    updatedAt: text('updated_at').notNull(),
    deletedAt: text('deleted_at'),
  },
  (table) => [
    check(
      'accounts_id',
      sql`${table.id} IS NOT NULL AND length(${table.id}) = 4 AND ${table.id} NOT GLOB '*[^0-9a-hjkmnp-tv-z]*'`,
    ),
    check('accounts_name', sql`length(trim(${table.name})) > 0`),
    check(
      'accounts_type',
      sql`${table.type} IN (${sql.raw(ACCOUNT_TYPES.map((type) => `'${type}'`).join(','))})`,
    ),
    check(
      'accounts_currency',
      sql`length(${table.currency}) = 3 AND ${table.currency} NOT GLOB '*[^A-Z]*'`,
    ),
    check('accounts_archived', sql`${table.archived} IN (0, 1)`),
    check(
      'accounts_opening_date',
      sql`${table.openingDate} IS NULL OR date(${table.openingDate}) IS ${table.openingDate}`,
    ),
    check(
      'accounts_opening_amount',
      sql`${table.openingAmount} = 0 OR ${table.openingDate} IS NOT NULL`,
    ),
    uniqueIndex('accounts_name_unique')
      .on(table.name)
      .where(sql`${table.deletedAt} IS NULL`),
  ],
)
