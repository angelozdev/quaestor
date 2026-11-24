import { ACCOUNT_TYPES } from '#core/ledger'
import {
  amountText,
  currencyCode,
  dateText,
  dryRun,
  emojiText,
  fields,
  oneOf,
  requiredText,
} from '../../invocation/input/input.schema.ts'

export const accountAddSchema = fields({
  name: requiredText,
  emoji: emojiText,
  type: oneOf(ACCOUNT_TYPES),
  currency: currencyCode,
  opening: amountText,
  openingDate: dateText,
  dryRun,
})
