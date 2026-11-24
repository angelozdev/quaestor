export const MANIFEST_FILE = 'manifest.json'

export const SHA256 = 'sha256'

export const HEX = 'hex'

export const LINE_BREAK = '\n'

export const SHA256_DIFFERS = 'sha256 differs from manifest.json'

export const NOT_JSON = 'is not valid JSON'

export const CANNOT_READ = 'cannot be read: '

export const USED_TABLES = ['account', 'category', 'tag', 'transaction', 'transaction_tag'] as const

export const CREATED_AT_PATTERN = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$/

export const WHOLE_MESSAGE = 'must be a whole number'

export const CENTS_MESSAGE = 'must be whole cents'

export const FLAG_MESSAGE = 'must be true or false'

export const CREATED_AT_MESSAGE = 'must be a date and time like 2026-11-24T03:03:33.123456'

export const PATH_SEPARATOR = '.'
