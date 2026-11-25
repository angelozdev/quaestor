import { dryRun, fields, requiredText } from '../../invocation/input/input.schema.ts'

export const categoryEditSchema = fields({ code: requiredText, group: requiredText, dryRun })
