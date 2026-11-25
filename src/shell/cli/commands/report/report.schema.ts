import { z } from 'zod'
import { dateText, fields, requiredText, tagText } from '../../invocation/input/input.schema.ts'

export const reportSchema = fields({
  from: dateText,
  to: dateText,
  byMonth: z.boolean().default(false),
  tag: tagText.optional(),
  withoutTag: tagText.optional(),
  payee: requiredText.optional(),
}).refine(({ from, to }) => to >= from, { path: ['to'], error: 'must not be before from' })
