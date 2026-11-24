import { decode, encode } from '@toon-format/toon'
import { describe, expect, it } from 'vitest'
import { ledgerCli } from '../../../../../tests/support/ledger/ledger.ts'
import { alreadyExists, invalidInput } from '../../../../../tests/support/refusals/refusals.ts'
import { expectWrite } from '../../../../../tests/support/writes/writes.ts'

const TAG = 'trip:japon-2027'

describe('quaestor tag add', () => {
  it('tag add creates a tag; tag list shows it', async () => {
    const cli = ledgerCli()

    const added = await cli.run(['tag', 'add', TAG])
    const listed = await cli.run(['tag', 'list'])

    expectWrite(added, false, { tag: TAG })
    expect(decode(listed.stdout)).toEqual({ tags: [TAG] })
  })

  it.for(['Trip Japón', 'Trip', 'trip_japon', '  '])(
    'a tag outside lowercase letters, digits, colons and dashes is refused (%j)',
    async (name) => {
      const run = await ledgerCli().run(['tag', 'add', name])

      expect(run).toEqual({
        code: 1,
        stdout: '',
        stderr: invalidInput('name: must be lowercase letters, digits, colons and dashes'),
      })
    },
  )

  it('a tag already there is refused', async () => {
    const cli = ledgerCli()
    await cli.run(['tag', 'add', TAG])

    const second = await cli.run(['tag', 'add', TAG])
    const listed = await cli.run(['tag', 'list'])

    expect(second).toEqual({ code: 1, stdout: '', stderr: alreadyExists('tag', TAG) })
    expect(decode(listed.stdout)).toEqual({ tags: [TAG] })
  })

  it('--dry-run on tag add shows the tag and writes nothing', async () => {
    const cli = ledgerCli()

    const dry = await cli.run(['tag', 'add', TAG, '--dry-run'])
    const listed = await cli.run(['tag', 'list'])

    expectWrite(dry, true, { tag: TAG })
    expect(listed.stdout).toBe(`${encode({ tags: [] })}\n`)
  })
})
