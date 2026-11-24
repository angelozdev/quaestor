import { z } from 'zod'
import {
  ARRIVING_AMOUNT_MESSAGE,
  LEAVING_AMOUNT_MESSAGE,
  NOTHING_TO_WRITE_MESSAGE,
  REPEATED_MESSAGE,
  ZERO_AMOUNT_MESSAGE,
} from '../../invocation/input/input.constants.ts'
import {
  amountText,
  dateText,
  fields,
  requiredText,
  tagText,
} from '../../invocation/input/input.schema.ts'

const movementAmount = amountText.refine((cents) => cents !== 0, {
  error: ZERO_AMOUNT_MESSAGE,
  abort: true,
})

const tagList = z
  .array(tagText)
  .check((ctx) => {
    for (const [index, tag] of ctx.value.entries())
      if (ctx.value.indexOf(tag) !== index)
        ctx.issues.push({
          code: 'custom',
          message: REPEATED_MESSAGE,
          input: ctx.value,
          path: [index],
        })
  })
  .default([])

const movement = fields({
  account: requiredText,
  date: dateText,
  payee: requiredText,
  amount: movementAmount,
  currency: requiredText,
  category: requiredText,
  tags: tagList,
  note: z
    .string()
    .optional()
    .transform((note) => note ?? null),
})

const half = movement.omit({ category: true })

const transfer = fields({
  from: half.extend({
    amount: movementAmount.refine((cents) => cents < 0, LEAVING_AMOUNT_MESSAGE),
  }),
  to: half.extend({ amount: movementAmount.refine((cents) => cents > 0, ARRIVING_AMOUNT_MESSAGE) }),
})

export const movementWriteSchema = fields({
  delete: z.array(requiredText).default([]),
  movements: z.array(movement).default([]),
  transfers: z.array(transfer).default([]),
}).check((ctx) => {
  const { delete: deleted, movements, transfers } = ctx.value
  if (deleted.length + movements.length + transfers.length === 0)
    ctx.issues.push({ code: 'custom', message: NOTHING_TO_WRITE_MESSAGE, input: ctx.value })
})
