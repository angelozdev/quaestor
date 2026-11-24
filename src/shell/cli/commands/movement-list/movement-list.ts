import { listMovements } from '#shell/db'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { DEFAULT_LIMIT } from './movement-list.constants.ts'
import { movementListSchema } from './movement-list.schema.ts'

export const movementListCommand: CliCommand = {
  name: 'list',
  group: 'movement',
  description: 'list movements, newest first, each with its account balance after it',
  options: [
    { flags: '--account <code>', description: 'only the movements of this account' },
    { flags: '--from <date>', description: 'from this day on, such as 2026-11-24' },
    { flags: '--to <date>', description: 'up to this day, included' },
    {
      flags: '--payee <text>',
      description: 'only payees containing this text, ignoring case and accents',
    },
    {
      flags: '--limit <n>',
      description: 'list at most this many, the newest first',
      defaultValue: DEFAULT_LIMIT,
    },
  ],
  run: (context, options, _args, flags) => {
    const { limit, ...filter } = parsed(movementListSchema, flags)
    return withStore(context, options, async (store) => {
      const matches = listMovements(store, filter)
      return { total: matches.length, movements: matches.slice(0, limit) }
    })
  },
}
