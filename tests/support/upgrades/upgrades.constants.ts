import { join } from 'node:path'
import { REPO_ROOT } from '#shell/cli'

export const SEEDS = join(REPO_ROOT, 'tests', 'support', 'upgrades')

export const TIMESTAMP_LENGTH = 14

export const SEED_NAME = '0_seed'
