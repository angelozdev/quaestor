export const MAX_WHOLE_PART = 1_000_000_000_000

export const MAX_DECIMAL_DIGITS = 2

export const SIGNS = ['', '-']

export const MAX_MOVEMENT_CENTS = 100_000_000_000

export const MAX_DAYS_AFTER = 700

export const MS_PER_DAY = 86_400_000

export const CENTS_PER_UNIT = 100

export const ISO_DATE_LENGTH = 10

export const BOOKED_ACCOUNTS = ['wallet', 'savings'] as const

export const MAX_BOOKED = 20

export const FAULTS = ['category', 'currency', 'opening'] as const

export const MAX_FAULTY_ITEMS = 8

export const MOVED_ACCOUNTS = ['wallet', 'savings', 'bank'] as const

export const MAX_MOVED = 8

export const LEGACY_FIRST_DAY = '2026-01-05'

export const LEGACY_CURRENCIES = ['USD', 'COP'] as const

export const LEGACY_KINDS = ['expense', 'income'] as const

export const LEGACY_STATUSES = ['posted', 'posted', 'skipped', 'planned'] as const

export const MAX_LEGACY_ACCOUNTS = 4

export const MAX_LEGACY_ENTRIES = 12

export const MAX_LEGACY_BALANCE_CENTS = 100_000_000_000

export const LEGACY_CREATED_AT = '2026-01-05T10:00:00'
