import { dryRun, fields, requiredText } from '../../invocation/input/input.schema.ts'

export const groupDeleteSchema = fields({ code: requiredText, dryRun })
