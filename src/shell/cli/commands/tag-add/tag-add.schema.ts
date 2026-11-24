import { dryRun, fields, tagText } from '../../invocation/input/input.schema.ts'

export const tagAddSchema = fields({ name: tagText, dryRun })
