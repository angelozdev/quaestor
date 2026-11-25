import { join } from 'node:path'
import { build } from 'rolldown'
import type { Release } from '#shell/cli'
import { BUNDLE_FILE, NODE_BUILTINS, RELEASE_CONSTANT, RELEASE_ENTRY } from './build.constants.ts'

export async function buildRelease(
  release: Release,
  outDir: string = release.repoRoot,
): Promise<void> {
  await build({
    input: join(release.repoRoot, RELEASE_ENTRY),
    platform: 'node',
    external: [NODE_BUILTINS],
    transform: { define: { [RELEASE_CONSTANT]: JSON.stringify(release) } },
    output: {
      file: join(outDir, BUNDLE_FILE),
      format: 'esm',
      minify: true,
    },
  })
}
