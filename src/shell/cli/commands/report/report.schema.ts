import { dateText, fields } from '../../invocation/input/input.schema.ts'

export const reportSchema = fields({ from: dateText, to: dateText }).refine(
  ({ from, to }) => to >= from,
  { path: ['to'], error: 'must not be before from' },
)
