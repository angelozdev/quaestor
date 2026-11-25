export const REQUIRED_MESSAGE = 'is required'

export const DATE_MESSAGE = 'must be a date like 2026-11-24'

export const AMOUNT_MESSAGE =
  'must be an amount like "-15000" or "-30.39": no thousands separator, at most 2 decimals'

export const AMOUNT_TOO_LARGE_MESSAGE = 'is too large: at most 90071992547409.91 either way'

export const CURRENCY_MESSAGE = 'must be an ISO 4217 code such as COP'

export const LOCAL_CURRENCY_MESSAGE = 'must not be COP, the local currency'

export const RATE_MESSAGE =
  'must be a rate like "3912.45": above 0, no thousands separator, at most 2 decimals'

export const RATE_TOO_LARGE_MESSAGE = 'is too large: at most 9999999999999.99'

export const EMOJI_MESSAGE = 'must be one emoji such as 🏦'

export const TAG_MESSAGE = 'must be lowercase letters, digits, colons and dashes'

export const UNKNOWN_KEY_MESSAGE = 'is not a field'

export const ZERO_AMOUNT_MESSAGE = 'must not be 0'

export const LEAVING_AMOUNT_MESSAGE = 'must be negative: the money leaves this account'

export const ARRIVING_AMOUNT_MESSAGE = 'must be positive: the money arrives in this account'

export const LIMIT_MESSAGE = 'must be a whole number above 0'

export const REPEATED_MESSAGE = 'is repeated'

export const NOTHING_TO_CHANGE_MESSAGE = 'nothing to change: give --name, --emoji or both'

export const NOTHING_TO_WRITE_MESSAGE = 'nothing to write: give delete, movements or transfers'

export const EMOJI_PATTERN = /^\p{RGI_Emoji}$/v

export const ISSUE_SEPARATOR = '; '

export const PATH_SEPARATOR = '.'

export const DRY_RUN_OPTION = {
  flags: '--dry-run',
  description: 'do everything but commit, and show what would change',
}
