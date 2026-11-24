import type { ExportRows, ExportTransaction } from './legacy-export.types.ts'

export const TABLE_NAMES = [
  'account',
  'alembic_version',
  'category',
  'category_group',
  'fund',
  'meta',
  'meta_amendment',
  'meta_contribution',
  'recurring_item',
  'recurring_occurrence',
  'settings',
  'tag',
  'transaction',
  'transaction_tag',
] as const

export const EXPORTED_AT = '2026-11-24T03:03:33Z'

export const UNPARSED_TABLES = {
  alembic_version: [{ version_num: '9f2c1a7b3d4e' }],
  category_group: [{ id: '1', name: 'Daily' }],
  settings: [{ key: 'usd_cop', value: '4000.000000' }],
}

export const MANIFEST_SOURCE = {
  container: 'quaestor-db-1',
  volume: 'quaestor_pg_data',
  lastWrite: '2026-11-23T20:00:00',
}

export const MANIFEST_DUMP = { file: 'final.dump', bytes: 1024, sha256: 'a'.repeat(64) }

export const MANIFEST_FORMAT = 'jsonl-row-to-json'

const GROUP = 'b7e1c0de-5a21-4c1e-9d0b-0a1b2c3d4e5f'

function posted(
  fields: Pick<ExportTransaction, 'id' | 'date' | 'payee' | 'amount' | 'accountId' | 'createdAt'> &
    Partial<ExportTransaction>,
): ExportTransaction {
  return {
    notes: null,
    type: 'expense',
    status: 'posted',
    categoryId: null,
    transferGroup: null,
    direction: null,
    ...fields,
  }
}

export const FIXTURE_ROWS: ExportRows = {
  accounts: [
    { id: 1, name: '💵 Wallet', type: 'debit', currency: 'USD', archived: false, balance: 9000 },
    { id: 2, name: '🏦 Bank', type: 'debit', currency: 'COP', archived: false, balance: 185000000 },
    {
      id: 3,
      name: '💳 Old Card',
      type: 'credit',
      currency: 'COP',
      archived: true,
      balance: -1500000,
    },
    { id: 9, name: '🤝 Loans', type: 'cash', currency: 'COP', archived: false, balance: 0 },
    { id: 10, name: '🐷 Piggy', type: 'savings', currency: 'USD', archived: false, balance: 5000 },
  ],
  categories: [
    { id: 1, name: '🍽️ Restaurants', archived: false },
    { id: 2, name: '🚕 Rideshare/Taxi', archived: false },
    { id: 3, name: '🎁 Gifts', archived: true },
    { id: 4, name: '🎁 Gifts', archived: false },
    { id: 5, name: 'Misc', archived: true },
    { id: 6, name: '🔁 Transfers', archived: false },
    { id: 7, name: '💰 Salary', archived: false },
  ],
  tags: [
    { id: 1, name: 'trip:lima-2026' },
    { id: 2, name: 'who:alex' },
  ],
  transactions: [
    posted({
      id: 3,
      date: '2026-11-22',
      payee: 'Dinner',
      amount: 5025,
      accountId: 1,
      categoryId: 1,
      notes: '',
      createdAt: '2026-11-22T20:15:00',
    }),
    posted({
      id: 4,
      date: '2026-12-01',
      payee: 'Rent',
      amount: 99999,
      accountId: 1,
      categoryId: 1,
      status: 'planned',
      createdAt: '2026-11-01T08:00:00.5',
    }),
    posted({
      id: 5,
      date: '2026-10-01',
      payee: 'Old',
      amount: 777,
      accountId: 1,
      categoryId: 1,
      status: 'skipped',
      createdAt: '2026-10-01T08:00:00',
    }),
    posted({
      id: 10,
      date: '2026-11-22',
      payee: 'Taxi',
      amount: 1500000,
      accountId: 2,
      categoryId: 2,
      createdAt: '2026-11-22T13:00:00.000001',
    }),
    posted({
      id: 9,
      date: '2026-11-22',
      payee: 'Almuerzo',
      amount: 3500000,
      accountId: 2,
      categoryId: 1,
      createdAt: '2026-11-22T12:00:00.000001',
    }),
    posted({
      id: 11,
      date: '2026-11-21',
      payee: 'Refund',
      amount: 2000,
      accountId: 1,
      categoryId: 1,
      type: 'income',
      notes: 'cambio a 4.000',
      createdAt: '2026-11-21T14:05:09.12345',
    }),
    posted({
      id: 14,
      date: '2026-11-20',
      payee: 'Uber',
      amount: 1250,
      accountId: 1,
      categoryId: 2,
      createdAt: '2026-11-20T09:30:01.1234',
    }),
    posted({
      id: 15,
      date: '2026-11-21',
      payee: 'To Bank',
      amount: 10000,
      accountId: 1,
      type: 'transfer',
      transferGroup: GROUP,
      direction: 'out',
      createdAt: '2026-11-21T16:00:00.987654',
    }),
    posted({
      id: 20,
      date: '2026-11-21',
      payee: 'From Wallet',
      amount: 40000000,
      accountId: 2,
      type: 'transfer',
      transferGroup: GROUP,
      direction: 'in_',
      createdAt: '2026-11-21T16:00:01.987654',
    }),
    posted({
      id: 21,
      date: '2026-11-23',
      payee: 'Reintegro',
      amount: -50000000,
      accountId: 2,
      categoryId: 6,
      createdAt: '2026-11-23T10:00:00',
    }),
    posted({
      id: 22,
      date: '2026-11-20',
      payee: 'Salary',
      amount: 100000000,
      accountId: 2,
      categoryId: 7,
      type: 'income',
      createdAt: '2026-11-20T08:00:00',
    }),
    posted({
      id: 30,
      date: '2026-10-15',
      payee: 'Netflix',
      amount: 2500000,
      accountId: 3,
      categoryId: 1,
      createdAt: '2026-10-15T09:00:00',
    }),
    posted({
      id: 31,
      date: '2026-10-20',
      payee: 'Reversal',
      amount: 1000000,
      accountId: 3,
      categoryId: 1,
      type: 'income',
      createdAt: '2026-10-20T09:00:00',
    }),
  ],
  tagLinks: [
    { transactionId: 11, tagId: 2 },
    { transactionId: 11, tagId: 1 },
    { transactionId: 14, tagId: 1 },
    { transactionId: 5, tagId: 1 },
  ],
}
