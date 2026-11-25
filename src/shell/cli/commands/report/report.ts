import { reportOf } from '#core/report'
import { countedMovements, listCategories, listGroups, listRates } from '#shell/db'
import { parsed } from '../../invocation/input/input.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'
import { reportSchema } from './report.schema.ts'

export const reportCommand: CliCommand = {
  name: 'report',
  description: 'spending and income of a period, by group and category',
  options: [
    { flags: '--from <day>', description: 'the first day, included, such as 2026-10-01' },
    { flags: '--to <day>', description: 'the last day, included, such as 2026-10-31' },
    { flags: '--by-month', description: 'split every table by calendar month, cut to the period' },
  ],
  run: (context, options, _args, flags) => {
    const request = parsed(reportSchema, flags)
    return withStore(context, options, async (store) =>
      reportOf(
        request,
        countedMovements(store, request),
        { groups: listGroups(store), categories: listCategories(store) },
        listRates(store),
      ),
    )
  },
}
