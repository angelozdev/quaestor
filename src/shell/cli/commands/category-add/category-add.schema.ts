import { dryRun, emojiText, fields, requiredText } from '../../invocation/input/input.schema.ts'

export const categoryAddSchema = fields({
  name: requiredText,
  emoji: emojiText,
  dryRun,
})
