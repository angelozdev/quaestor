import { NOTHING_TO_CHANGE_MESSAGE } from '../../invocation/input/input.constants.ts'
import { dryRun, emojiText, fields, requiredText } from '../../invocation/input/input.schema.ts'

export const groupEditSchema = fields({
  code: requiredText,
  name: requiredText.optional(),
  emoji: emojiText.optional(),
  dryRun,
}).refine(({ name, emoji }) => name !== undefined || emoji !== undefined, {
  error: NOTHING_TO_CHANGE_MESSAGE,
})
