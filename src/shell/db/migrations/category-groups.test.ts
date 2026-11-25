import { decode, encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { shippedMigration, upgradeCli } from '../../../../tests/support/upgrades/upgrades.ts'

const APPROVED_PLACES: Record<string, string[]> = {
  xwvq: ['Rent', 'Home Maintenance', 'Laundry'],
  jpnq: ['Utilities', 'Services', 'Internet', 'Phone'],
  '1aae': ['Restaurants', 'Groceries', 'Food Delivery', 'Coffee Shops', 'Food'],
  y6v7: [
    'Gas',
    'Parking',
    'Tolls',
    'Car Wash',
    'Car Maintenance',
    'Auto Insurance',
    'Rideshare/Taxi',
    'Car Payment',
  ],
  q3rh: ['Clothing', 'Gadgets', 'Home Goods', 'Pets'],
  cx75: ['Healthcare', 'Fitness', 'Beauty & Wellness'],
  ex09: ['Entertainment', 'Streaming', 'Fun'],
  xgn8: ['Flights', 'Car Rental', 'Lodging'],
  pjbv: ['AI Tools', 'Software'],
  d7gd: ['Courses / Learning'],
  zyt4: ['Gifts'],
  '3asb': ['Taxes', 'Accountant', 'Bank Fees', 'Refund', 'Reimbursable'],
  m0z7: ['Salary', 'Bonuses', 'Interest', 'Cashback'],
  '7hdg': ['Payment / Transfer', 'Investment', 'Investment Gains'],
}

const SEEDED_CODES = Array.from({ length: 50 }, (_, index) => `c0${String(index).padStart(2, '0')}`)

type Listed = { id: string; group: string; name: string; archived: boolean }

function approvedGroupOf(name: string): string | undefined {
  return Object.entries(APPROVED_PLACES).find(([, names]) => names.includes(name))?.[0]
}

const UNDER_TEST = shippedMigration('category_groups')

describe('the category_groups upgrade', () => {
  it('the upgrade puts every existing category in its approved group, archived ones by their name', async () => {
    const cli = upgradeCli('category-groups.sql', UNDER_TEST)
    await cli.before(['movement', 'list'])

    const { code, stdout } = await cli.after(['category', 'list'])

    expect(code).toBe(0)
    const { categories } = decode(stdout) as { categories: Listed[] }
    expect(categories.map(({ id }) => id).toSorted()).toEqual(SEEDED_CODES)
    expect(categories.filter(({ archived }) => archived)).toEqual([
      { id: 'c048', group: 'y6v7', emoji: '🏷️', name: 'Auto Insurance', archived: true },
    ])
    for (const { id, group, name } of categories)
      expect(group, `${id} ${name}`).toBe(approvedGroupOf(name))
  })

  it('the upgrade keeps every movement on its category', async () => {
    const cli = upgradeCli('category-groups.sql', UNDER_TEST)
    const before = await cli.before(['movement', 'list'])

    const after = await cli.after(['movement', 'list'])

    expect(before.code).toBe(0)
    expect(after.code).toBe(0)
    expect(after.stdout).toBe(before.stdout)
    expect(decode(after.stdout)).toMatchObject({
      total: 2,
      movements: [{ category: 'c041' }, { category: 'c007' }],
    })
  })

  it('a category the list does not name stops the upgrade and leaves the store as it was', async () => {
    const cli = upgradeCli('unknown-category.sql', UNDER_TEST)
    const before = await cli.before(['movement', 'list'])
    const reason = 'NOT NULL constraint failed: categories.group_id'
    const failed = {
      code: 2,
      stdout: '',
      stderr: `env: test\n${encode({
        error: {
          code: 'migration_failed',
          migration: UNDER_TEST,
          reason,
          message: `migration ${UNDER_TEST} failed: ${reason}`,
        },
      })}\n`,
    }

    const attempt = await cli.after(['category', 'list'])
    const untouched = await cli.before(['movement', 'list'])
    const again = await cli.after(['category', 'list'])

    expect(attempt).toEqual(failed)
    expect(untouched).toEqual({ code: 0, stdout: before.stdout, stderr: 'env: test\n' })
    expect(again).toEqual(failed)
  })
})
