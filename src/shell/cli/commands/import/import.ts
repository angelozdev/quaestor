import { expectedBalances, ledgerFrom } from '#core/legacy'
import { importLedger, inTransaction, listAccounts, type Store } from '#shell/db'
import { readLegacyExport } from '#shell/legacy'
import { DRY_RUN_OPTION } from '../../invocation/input/input.constants.ts'
import { withStore } from '../../invocation/with-store/with-store.ts'
import type { CliCommand } from '../../main/main.types.ts'

function openingsOf(store: Store) {
  return listAccounts(store)
    .filter(({ openingAmount }) => openingAmount !== 0)
    .map(({ id, name, openingAmount, currency, openingDate }) => ({
      account: id,
      name,
      amount: openingAmount,
      currency,
      date: openingDate,
    }))
}

export const importCommand: CliCommand = {
  name: 'import',
  description: 'import the legacy export, once, into an empty store',
  argument: { name: 'folder', description: 'the legacy export folder, such as ~/.quaestor/legacy' },
  options: [DRY_RUN_OPTION],
  run: async (context, options, args, flags) => {
    const legacy = await readLegacyExport(args[0])
    const ledger = ledgerFrom(legacy, context.randomIndex)
    const expected = expectedBalances(legacy, ledger)
    const dryRun = flags.dryRun === true
    return withStore(context, options, async (store) => ({
      dryRun,
      ...inTransaction(store, dryRun, () => ({
        imported: importLedger(store, ledger, expected, context.clock()),
        openings: openingsOf(store),
      })),
    }))
  },
}
