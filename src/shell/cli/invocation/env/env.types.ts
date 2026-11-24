import type { Vars } from '../../main/main.types.ts'

export type EnvSources = {
  flag: string | undefined
  vars: Vars
  defaultEnv: string
  releaseOnlyEnvs: string[]
  dataDir: string | null
}

export type Env = { name: string; dbPath: string }
