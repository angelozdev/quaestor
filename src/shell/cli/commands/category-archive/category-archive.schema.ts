import { dryRun, fields, requiredText } from '../../invocation/input/input.schema.ts'

export const categoryArchiveSchema = fields({ code: requiredText, dryRun })
