import { z } from 'zod'
import { LIMIT_MESSAGE } from '../../invocation/input/input.constants.ts'
import { dateText, fields, requiredText } from '../../invocation/input/input.schema.ts'
import { LIMIT_PATTERN } from './movement-list.constants.ts'

const limitText = z
  .string()
  .regex(LIMIT_PATTERN, LIMIT_MESSAGE)
  .transform(Number)
  .refine((limit) => limit > 0, LIMIT_MESSAGE)

export const movementListSchema = fields({
  account: requiredText.optional(),
  from: dateText.optional(),
  to: dateText.optional(),
  payee: requiredText.optional(),
  limit: limitText,
})
