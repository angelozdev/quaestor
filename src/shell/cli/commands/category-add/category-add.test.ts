import { decode, encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import {
  alreadyExists,
  invalidInput,
  notFound,
} from '../../../../../tests/support/refusals/refusals.ts'
import { expectWrite } from '../../../../../tests/support/writes/writes.ts'

const CODE = /^[0-9a-hjkmnp-tv-z]{4}$/

const GAMES = {
  id: expect.stringMatching(CODE),
  group: 'ex09',
  emoji: '🎮',
  name: 'Games',
  archived: false,
}

function addArgv(name = 'Games', emoji = '🎮', group = 'ex09'): string[] {
  return ['category', 'add', name, '--emoji', emoji, '--group', group]
}

function repeatingDraw() {
  const indexes = [0, 1, 2, 3, 0, 1, 2, 3, 4, 5, 6, 7]
  let draws = 0
  return () => indexes[draws++]!
}

describe('quaestor category add', () => {
  it('a category is created with its group, and category list shows it', async () => {
    const cli = ledgerCli()

    const added = await cli.run(addArgv('Gifts', '🎁', 'zyt4'))
    const listed = await cli.run(['category', 'list'])

    const { id } = (decode(added.stdout) as { category: { id: string } }).category
    expect(added).toEqual({
      code: 0,
      stdout: `${encode({
        dryRun: false,
        category: { id, group: 'zyt4', emoji: '🎁', name: 'Gifts', archived: false },
      })}\n`,
      stderr: 'env: test\n',
    })
    expect(listed.stdout).toBe(
      `categories[1]{id,group,emoji,name,archived}:\n  ${encode(id)},zyt4,🎁,Gifts,false\n`,
    )
  })

  it('the group is required', async () => {
    const run = await ledgerCli().run(['category', 'add', 'Games', '--emoji', '🎮'])

    expect(run).toEqual({ code: 1, stdout: '', stderr: invalidInput('group: is required') })
  })

  it('a group that does not exist is refused as not_found', async () => {
    const cli = ledgerCli()

    const run = await cli.run(addArgv('Games', '🎮', 'zzzz'))
    const listed = await cli.run(['category', 'list'])

    expect(run).toEqual({ code: 1, stdout: '', stderr: notFound('group', 'zzzz') })
    expect(listed.stdout).toBe(`${encode({ categories: [] })}\n`)
  })

  it('category add creates a category and category list shows it with its code', async () => {
    const cli = ledgerCli()

    const added = await cli.run(addArgv())
    const listed = await cli.run(['category', 'list'])

    expectWrite(added, false, { category: GAMES })
    expect(decode(listed.stdout)).toEqual({ categories: [GAMES] })
  })

  it('a category keeps its emoji apart from its name', async () => {
    const cli = ledgerCli()
    await cli.run(addArgv('Restaurants', '🍽️'))

    const { stdout } = await cli.run(['category', 'list'])

    expect(decode(stdout)).toMatchObject({ categories: [{ emoji: '🍽️', name: 'Restaurants' }] })
  })

  it('an unknown category name can be added once; a second active one is refused', async () => {
    const cli = ledgerCli()
    await cli.run(addArgv())

    const second = await cli.run(addArgv('Games', '🕹️'))
    const listed = await cli.run(['category', 'list'])

    expect(second).toEqual({ code: 1, stdout: '', stderr: alreadyExists('category', 'Games') })
    expect(decode(listed.stdout)).toEqual({ categories: [GAMES] })
  })

  it('two categories never share a code, even when the draw repeats', async () => {
    const cli = ledgerCli({ randomIndex: repeatingDraw() })

    const first = await cli.run(addArgv())
    const second = await cli.run(addArgv('Books', '📚'))
    const listed = await cli.run(['category', 'list'])

    expect(first.code).toBe(0)
    expect(second.code).toBe(0)
    expect(decode(listed.stdout)).toMatchObject({
      categories: [
        { id: '4567', name: 'Books' },
        { id: '0123', name: 'Games' },
      ],
    })
  })

  it('--dry-run on category add shows the category and writes nothing', async () => {
    const cli = ledgerCli()

    const dry = await cli.run([...addArgv(), '--dry-run'])
    const listed = await cli.run(['category', 'list'])

    expectWrite(dry, true, { category: GAMES })
    expect(listed.stdout).toBe(`${encode({ categories: [] })}\n`)
  })

  it.for(['🎮🎮', 'A'])(
    'an emoji field that is not exactly one emoji is refused (%s)',
    async (emoji) => {
      const run = await ledgerCli().run(addArgv('Games', emoji))

      expect(run).toEqual({
        code: 1,
        stdout: '',
        stderr: invalidInput('emoji: must be one emoji such as 🏦'),
      })
    },
  )

  it('the emoji is required', async () => {
    const run = await ledgerCli().run(['category', 'add', 'Games', '--group', 'ex09'])

    expect(run).toEqual({ code: 1, stdout: '', stderr: invalidInput('emoji: is required') })
  })

  it('a category name with no text is refused', async () => {
    const run = await ledgerCli().run(addArgv('  '))

    expect(run).toEqual({ code: 1, stdout: '', stderr: invalidInput('name: is required') })
  })
})
