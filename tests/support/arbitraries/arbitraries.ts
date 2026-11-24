import fc from 'fast-check'
import { MAX_DECIMAL_DIGITS, MAX_WHOLE_PART, SIGNS } from './arbitraries.constants.ts'

export const amountText = fc
  .tuple(
    fc.constantFrom(...SIGNS),
    fc.integer({ min: 0, max: MAX_WHOLE_PART }),
    fc.array(fc.integer({ min: 0, max: 9 }), { maxLength: MAX_DECIMAL_DIGITS }),
  )
  .map(
    ([sign, whole, decimals]) =>
      `${sign}${whole}${decimals.length === 0 ? '' : `.${decimals.join('')}`}`,
  )
