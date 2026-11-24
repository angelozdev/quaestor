export const ACCOUNT_TYPES = ['savings', 'debit', 'credit', 'cash'] as const

export const ID_ALPHABET = '0123456789abcdefghjkmnpqrstvwxyz'

export const ID_LENGTH = 4

export const AMOUNT_PATTERN = /^-?\d+(\.\d{1,2})?$/

export const DECIMAL_DIGITS = 2

export const CENTS_PER_UNIT = 100

export const CURRENCIES = new Set(Intl.supportedValuesOf('currency'))
