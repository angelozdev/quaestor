export const REQUIRED_MESSAGE = 'is required'

export const DATE_MESSAGE = 'must be a date like 2026-11-24'

export const AMOUNT_MESSAGE =
  'must be an amount like "-15000" or "-30.39": no thousands separator, at most 2 decimals'

export const CURRENCY_MESSAGE = 'must be an ISO 4217 code such as COP'

export const EMOJI_MESSAGE = 'must be one emoji such as 🏦'

export const UNKNOWN_KEY_MESSAGE = 'is not a field'

export const EMOJI_PATTERN = /^\p{RGI_Emoji}$/v

export const ISSUE_SEPARATOR = '; '

export const PATH_SEPARATOR = '.'

export const DRY_RUN_OPTION = {
  flags: '--dry-run',
  description: 'do everything but commit, and show what would change',
}
