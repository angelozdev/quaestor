import { GROUP_KINDS } from '#core/ledger'
import {
  dryRun,
  emojiText,
  fields,
  oneOf,
  requiredText,
} from '../../invocation/input/input.schema.ts'

export const groupAddSchema = fields({
  name: requiredText,
  emoji: emojiText,
  kind: oneOf(GROUP_KINDS),
  dryRun,
})
