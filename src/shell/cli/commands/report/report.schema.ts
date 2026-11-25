import { z } from 'zod'
import { dateText, fields } from '../../invocation/input/input.schema.ts'

export const reportSchema = fields({
  from: dateText,
  to: dateText,
  byMonth: z.boolean().default(false),
}).refine(({ from, to }) => to >= from, { path: ['to'], error: 'must not be before from' })
