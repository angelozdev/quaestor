import { z } from 'zod'
import { fields } from '../../invocation/input/input.schema.ts'

export const accountListSchema = fields({ all: z.boolean().default(false) })
