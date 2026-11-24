export type RunResult = { status: number; stdout: string; stderr: string }

export type RunOptions = { cwd?: string }

export type Runner = (command: string, args: string[], options?: RunOptions) => Promise<RunResult>
