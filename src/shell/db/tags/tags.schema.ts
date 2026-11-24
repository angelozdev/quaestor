import { sql } from 'drizzle-orm'
import { check, sqliteTable, text } from 'drizzle-orm/sqlite-core'

export const tags = sqliteTable(
  'tags',
  {
    name: text().primaryKey(),
    createdAt: text('created_at').notNull(),
    updatedAt: text('updated_at').notNull(),
    deletedAt: text('deleted_at'),
  },
  (table) => [
    check(
      'tags_name',
      sql`${table.name} IS NOT NULL AND length(${table.name}) > 0 AND ${table.name} NOT GLOB '*[^a-z0-9:-]*'`,
    ),
  ],
)
