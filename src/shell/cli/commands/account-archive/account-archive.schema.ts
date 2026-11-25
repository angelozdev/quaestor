import { dryRun, fields, requiredText } from '../../invocation/input/input.schema.ts'

export const accountArchiveSchema = fields({ code: requiredText, dryRun })
