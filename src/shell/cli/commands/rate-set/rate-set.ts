import { inTransaction, setRate } from '#shell/db'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { rateSetSchema } from './rate-set.schema.ts'

export const rateSetCommand: CliCommand = {
  name: 'set',
  group: 'rate',
  description: 'set the COP that one unit of a foreign currency is worth, replacing the old rate',
  arguments: [
    { name: 'currency', description: 'an ISO 4217 code other than COP, such as USD' },
    { name: 'rate', description: 'the COP per unit, as text such as "3912.45"' },
  ],
  options: [DRY_RUN_OPTION],
  run: (context, options, args, flags) => {
    const { currency, rate, dryRun } = parsed(rateSetSchema, {
      currency: args[0],
      rate: args[1],
      ...flags,
    })
    return withStore(context, options, async (store) => ({
      dryRun,
      rate: inTransaction(store, dryRun, () => setRate(store, currency, rate, context.clock())),
    }))
  },
}
