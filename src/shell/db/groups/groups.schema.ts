import { sql } from 'drizzle-orm'
import { check, sqliteTable, text, uniqueIndex } from 'drizzle-orm/sqlite-core'
import { GROUP_KINDS, type GroupKind } from '#core/ledger'

export const groups = sqliteTable(
  'groups',
  {
    id: text().primaryKey(),
    kind: text().$type<GroupKind>().notNull(),
    emoji: text().notNull(),
    name: text().notNull(),
    createdAt: text('created_at').notNull(),
    updatedAt: text('updated_at').notNull(),
    deletedAt: text('deleted_at'),
  },
  (table) => [
    check(
      'groups_id',
      sql`${table.id} IS NOT NULL AND length(${table.id}) = 4 AND ${table.id} NOT GLOB '*[^0-9a-hjkmnp-tv-z]*'`,
    ),
    check('groups_name', sql`length(trim(${table.name})) > 0`),
    check(
      'groups_kind',
      sql`${table.kind} IN (${sql.raw(GROUP_KINDS.map((kind) => `'${kind}'`).join(','))})`,
    ),
    uniqueIndex('groups_name_unique')
      .on(table.name)
      .where(sql`${table.deletedAt} IS NULL`),
  ],
)
