import { isAbsolute } from 'node:path'
import { z } from 'zod'
import { ENV_NAME_PATTERN } from './env.constants.ts'

export const envNameSchema = z.string().regex(ENV_NAME_PATTERN)

export const dbPathSchema = z.string().refine(isAbsolute)
