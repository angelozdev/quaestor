export const ExitCode = { Success: 0, Refused: 1, Failed: 2 } as const

export const JSON_FLAG = '--json'

export const HELP_FLAG = '--help'

export const COMMAND_GROUPS = {
  account: 'accounts and their balances',
  category: 'categories a movement can take',
  tag: 'tags a movement can carry',
  movement: 'movements and transfers',
} as const
