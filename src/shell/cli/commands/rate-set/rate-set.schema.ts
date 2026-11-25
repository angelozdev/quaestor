import { dryRun, fields, foreignCurrency, rateText } from '../../invocation/input/input.schema.ts'

export const rateSetSchema = fields({ currency: foreignCurrency, rate: rateText, dryRun })
