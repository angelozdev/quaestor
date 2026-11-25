import { sql } from 'drizzle-orm'
import { check, integer, sqliteTable, text, uniqueIndex } from 'drizzle-orm/sqlite-core'
import { groups } from '../groups/groups.schema.ts'

export const categories = sqliteTable(
  'categories',
  {
    id: text().primaryKey(),
    emoji: text(),
    name: text().notNull(),
    archived: integer({ mode: 'boolean' }).notNull().default(false),
    createdAt: text('created_at').notNull(),
    updatedAt: text('updated_at').notNull(),
    deletedAt: text('deleted_at'),
    group: text('group_id')
      .notNull()
      .references(() => groups.id),
  },
  (table) => [
    check(
      'categories_id',
      sql`${table.id} IS NOT NULL AND length(${table.id}) = 4 AND ${table.id} NOT GLOB '*[^0-9a-hjkmnp-tv-z]*'`,
    ),
    check('categories_name', sql`length(trim(${table.name})) > 0`),
    check('categories_archived', sql`${table.archived} IN (0, 1)`),
    uniqueIndex('categories_name_unique')
      .on(table.name)
      .where(sql`${table.archived} = 0 AND ${table.deletedAt} IS NULL`),
  ],
)
