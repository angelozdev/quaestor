import { z } from 'zod'
import { ACCOUNT_TYPES } from '#core/ledger'
import {
  CENTS_MESSAGE,
  CREATED_AT_MESSAGE,
  CREATED_AT_PATTERN,
  FLAG_MESSAGE,
  WHOLE_MESSAGE,
} from './export.constants.ts'

const whole = z.string().regex(/^\d+$/, WHOLE_MESSAGE).transform(Number)

const cents = z
  .string()
  .regex(/^-?\d+$/, CENTS_MESSAGE)
  .transform(Number)
  .refine(Number.isSafeInteger, CENTS_MESSAGE)

const flag = z.enum(['true', 'false'], FLAG_MESSAGE).transform((value) => value === 'true')

export const manifestSchema = z.object({
  exportedAt: z.iso.datetime(),
  tables: z.array(
    z.object({
      name: z.string(),
      file: z.string(),
      rows: z.number().int().nonnegative(),
      sha256: z.string(),
    }),
  ),
  accounts: z.array(z.object({ id: whole, balance: cents })),
})

export const accountSchema = z.object({
  id: whole,
  name: z.string(),
  type: z.enum(ACCOUNT_TYPES),
  currency: z.string(),
  archived: flag,
})

export const categorySchema = z.object({ id: whole, name: z.string(), archived: flag })

export const tagSchema = z.object({ id: whole, name: z.string() })

export const transactionSchema = z
  .object({
    id: whole,
    date: z.iso.date(),
    payee: z.string(),
    notes: z.string().nullable(),
    type: z.enum(['expense', 'income', 'transfer']),
    status: z.enum(['posted', 'skipped', 'planned']),
    amount: cents,
    account_id: whole,
    category_id: whole.nullable(),
    transfer_group_id: z.string().nullable(),
    transfer_direction: z.enum(['out', 'in_']).nullable(),
    created_at: z.string().regex(CREATED_AT_PATTERN, CREATED_AT_MESSAGE),
  })
  .transform(
    ({
      account_id: accountId,
      category_id: categoryId,
      transfer_group_id: transferGroup,
      transfer_direction: direction,
      created_at: createdAt,
      ...rest
    }) => ({ ...rest, accountId, categoryId, transferGroup, direction, createdAt }),
  )

export const tagLinkSchema = z
  .object({ transaction_id: whole, tag_id: whole })
  .transform(({ transaction_id: transactionId, tag_id: tagId }) => ({ transactionId, tagId }))
