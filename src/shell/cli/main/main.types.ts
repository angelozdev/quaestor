export type Output = { write(chunk: string): unknown }

export type CliContext = {
  stdout: Output
  stderr: Output
  version: string
}
