import { spawn } from 'node:child_process'
import { cpSync, mkdirSync, symlinkSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { describe, it, type ExpectStatic } from 'vitest'
import { REPO_ROOT } from '#shell/cli'
import { tempDir } from '../support/temp-dir/temp-dir.ts'
import type { OnTestFinished } from '../support/temp-dir/temp-dir.types.ts'
import type { LintResult } from './lint.types.ts'

const oxlint = join(REPO_ROOT, 'node_modules', '.bin', 'oxlint')

function runOxlint(cwd: string, roots: string[]): Promise<LintResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(oxlint, roots, { cwd })
    let output = ''
    child.stdout.on('data', (chunk: Buffer) => (output += chunk.toString()))
    child.stderr.on('data', (chunk: Buffer) => (output += chunk.toString()))
    child.on('error', reject)
    child.on('close', (status, signal) =>
      status === null
        ? reject(new Error(`oxlint was ended by ${signal}`))
        : resolve({ status, output }),
    )
  })
}

function lintFixture(
  onFinished: OnTestFinished,
  files: Record<string, string>,
): Promise<LintResult> {
  const dir = tempDir('quaestor-lint-', onFinished)
  cpSync(join(REPO_ROOT, '.oxlintrc.json'), join(dir, '.oxlintrc.json'))
  cpSync(join(REPO_ROOT, 'tools'), join(dir, 'tools'), { recursive: true })
  symlinkSync(join(REPO_ROOT, 'node_modules'), join(dir, 'node_modules'))
  for (const [path, content] of Object.entries(files)) {
    const file = join(dir, path)
    mkdirSync(dirname(file), { recursive: true })
    writeFileSync(file, content)
  }
  return runOxlint(dir, [...new Set(Object.keys(files).map((path) => path.split('/')[0]))])
}

function lintEach(
  onFinished: OnTestFinished,
  paths: string[],
  source: string,
): Promise<LintResult[]> {
  return Promise.all(paths.map((path) => lintFixture(onFinished, { [path]: source })))
}

function expectFailure(expect: ExpectStatic, result: LintResult, ...mentions: string[]) {
  expect(result.status).not.toBe(0)
  for (const mention of mentions) expect(result.output).toContain(mention)
}

function expectPass(expect: ExpectStatic, result: LintResult, path: string) {
  expect(result.output).not.toContain(path)
  expect(result.status).toBe(0)
}

function expectEachFailure(
  expect: ExpectStatic,
  results: LintResult[],
  paths: string[],
  ...mentions: string[]
) {
  results.forEach((result, index) => expectFailure(expect, result, paths[index], ...mentions))
}

function expectEachPass(expect: ExpectStatic, results: LintResult[], paths: string[]) {
  results.forEach((result, index) => expectPass(expect, result, paths[index]))
}

const coreFile = 'src/core/sample/sample.ts'

const nodeImport = "import { readFileSync } from 'node:fs'\nexport const read = readFileSync\n"

const sqliteImport =
  "import { DatabaseSync } from 'node:sqlite'\nexport const open = DatabaseSync\n"

const drizzleImport = "import { sql } from 'drizzle-orm'\nexport const query = sql\n"

const shellImport = "import { openStore } from '#shell/db'\nexport const open = openStore\n"

const justImport = "import groupBy from 'just-group-by'\nexport const group = groupBy\n"

const justSubpathImport = "import pick from 'just-pick/index.mjs'\nexport const choose = pick\n"

const justDeepSubpathImport =
  "import group from 'just-group-by/a/b/c.js'\nexport const choose = group\n"

const mkdtempSyncImport = "import { mkdtempSync } from 'node:fs'\nexport const make = mkdtempSync\n"

const justMessage = 'only src/core/utils wraps just-* packages'

describe.concurrent('lint', () => {
  it('fails naming a src/core file that imports node:*', async ({ expect, onTestFinished }) => {
    const result = await lintFixture(onTestFinished, { [coreFile]: nodeImport })

    expectFailure(expect, result, coreFile, 'src/core performs no I/O')
  })

  it('fails when src/core imports drizzle-orm or #shell/*', async ({ expect, onTestFinished }) => {
    const [drizzle, shell] = await Promise.all([
      lintFixture(onTestFinished, { [coreFile]: drizzleImport }),
      lintFixture(onTestFinished, { [coreFile]: shellImport }),
    ])

    expectFailure(expect, drizzle, coreFile, 'only src/shell/db knows the ORM')
    expectFailure(expect, shell, coreFile, 'src/core never imports the shell')
  })

  it('fails when a file outside src/shell/db imports node:sqlite or drizzle-orm, and passes inside src/shell/db', async ({
    expect,
    onTestFinished,
  }) => {
    const outside = ['src/shell/cli/sample.ts', 'src/shell/cli/sample.test.ts']
    const inside = ['src/shell/db/sample.ts', 'src/shell/db/sample.test.ts']

    const [sqliteOutside, drizzleOutside, sqliteInside, drizzleInside] = await Promise.all([
      lintEach(onTestFinished, outside, sqliteImport),
      lintEach(onTestFinished, outside, drizzleImport),
      lintEach(onTestFinished, inside, sqliteImport),
      lintEach(onTestFinished, inside, drizzleImport),
    ])

    expectEachFailure(expect, sqliteOutside, outside, 'only src/shell/db knows the database')
    expectEachFailure(expect, drizzleOutside, outside, 'only src/shell/db knows the database')
    expectEachPass(expect, sqliteInside, inside)
    expectEachPass(expect, drizzleInside, inside)
  })

  it('fails when a file outside src/core/utils imports a just-* package, and passes inside it', async ({
    expect,
    onTestFinished,
  }) => {
    const outside = [
      'src/shell/cli/sample.ts',
      'src/shell/cli/sample.test.ts',
      'src/shell/db/sample.ts',
      'src/shell/db/sample.test.ts',
      'src/core/sample/sample.ts',
      'tests/sample/sample.test.ts',
      'tests/support/temp-dir/sample.ts',
      'tests/support/store/sample.ts',
    ]
    const inside = ['src/core/utils/sample.ts']

    const [outsideResults, subpathResults, deepSubpathResults, insideResults] = await Promise.all([
      lintEach(onTestFinished, outside, justImport),
      lintEach(onTestFinished, outside, justSubpathImport),
      lintEach(onTestFinished, outside, justDeepSubpathImport),
      lintEach(onTestFinished, inside, justImport),
    ])

    expectEachFailure(expect, outsideResults, outside, justMessage)
    expectEachFailure(expect, subpathResults, outside, justMessage)
    expectEachFailure(expect, deepSubpathResults, outside, justMessage)
    expectEachPass(expect, insideResults, inside)
  })

  it('passes an import whose path only contains just-, outside src/core/utils', async ({
    expect,
    onTestFinished,
  }) => {
    const importing = 'src/shell/cli/just-added.ts'
    const local = 'src/shell/cli/just-it.ts'

    const result = await lintFixture(onTestFinished, {
      [local]: 'export const a = 1\n',
      [importing]: [
        "import { a } from './just-it.ts'",
        "import b from '#core/just-x'",
        "import c from '@scope/just-pick'",
        'export const all = [a, b, c]',
        '',
      ].join('\n'),
    })

    expectPass(expect, result, importing)
    expectPass(expect, result, local)
  })

  it('fails when src/core/utils imports node:*, drizzle-orm or #shell/*', async ({
    expect,
    onTestFinished,
  }) => {
    const utilsFile = 'src/core/utils/sample.ts'
    const cases = [
      [nodeImport, 'src/core performs no I/O'],
      [drizzleImport, 'only src/shell/db knows the ORM'],
      [shellImport, 'src/core never imports the shell'],
    ]

    const results = await Promise.all(
      cases.map(([source]) => lintFixture(onTestFinished, { [utilsFile]: source })),
    )

    results.forEach((result, index) => expectFailure(expect, result, utilsFile, cases[index][1]))
  })

  it('fails naming a file with a comment, passes a shebang, and reports an oxlint-disable comment itself', async ({
    expect,
    onTestFinished,
  }) => {
    const [comments, shebang, disable] = await Promise.all([
      lintFixture(onTestFinished, {
        'src/shell/sample.ts': '// note\nexport const a = 1\n',
        'src/shell/other.ts': '/* note */\nexport const b = 2\n',
      }),
      lintFixture(onTestFinished, {
        'src/shell/bin.ts': '#!/usr/bin/env node\nexport const a = 1\n',
      }),
      lintFixture(onTestFinished, {
        'src/shell/disabled.ts': '// oxlint-disable\nexport const a = 1\n',
      }),
    ])

    expectFailure(expect, comments, 'src/shell/sample.ts', 'src/shell/other.ts', 'no-comments')
    expectPass(expect, shebang, 'src/shell/bin.ts')
    expectFailure(expect, disable, 'src/shell/disabled.ts', 'no-comments')
  })

  it('fails a file name that is not kebab-case', async ({ expect, onTestFinished }) => {
    const result = await lintFixture(onTestFinished, {
      'src/shell/SampleFile.ts': 'export const a = 1\n',
    })

    expectFailure(expect, result, 'src/shell/SampleFile.ts', 'filename-case')
  })

  it('fails a function above cognitive complexity 15', async ({ expect, onTestFinished }) => {
    const nested = (depth: number): string =>
      depth === 0 ? 'return 1' : `if (n > ${depth}) { ${nested(depth - 1)} }`
    const result = await lintFixture(onTestFinished, {
      'src/shell/complex.ts': `export function complex(n: number) { ${nested(6)}; return 0 }\n`,
    })

    expectFailure(expect, result, 'src/shell/complex.ts', 'cognitive-complexity')
  })

  it.for([
    ['mkdtempSync from node:fs', mkdtempSyncImport],
    ['mkdtemp from node:fs', "import { mkdtemp } from 'node:fs'\nexport const make = mkdtemp\n"],
    [
      'mkdtemp from node:fs/promises',
      "import { mkdtemp } from 'node:fs/promises'\nexport const make = mkdtemp\n",
    ],
  ])(
    'fails when a test file imports %s instead of using tempDir',
    async ([, source], { expect, onTestFinished }) => {
      const testFiles = [
        'src/shell/cli/sample.test.ts',
        'src/shell/db/sample.test.ts',
        'tests/sample/sample.test.ts',
      ]

      const results = await lintEach(onTestFinished, testFiles, source)

      expectEachFailure(expect, results, testFiles, 'tests make temp folders with tempDir')
    },
  )

  it('tests/support/store may import node:sqlite but not drizzle-orm', async ({
    expect,
    onTestFinished,
  }) => {
    const storeFile = 'tests/support/store/sample.ts'

    const [sqlite, drizzle] = await Promise.all([
      lintFixture(onTestFinished, { [storeFile]: sqliteImport }),
      lintFixture(onTestFinished, { [storeFile]: drizzleImport }),
    ])

    expectPass(expect, sqlite, storeFile)
    expectFailure(expect, drizzle, storeFile, 'only src/shell/db knows the ORM')
  })

  it('fails when tests/support/store imports mkdtemp instead of using tempDir', async ({
    expect,
    onTestFinished,
  }) => {
    const storeFile = 'tests/support/store/sample.ts'

    const result = await lintFixture(onTestFinished, { [storeFile]: mkdtempSyncImport })

    expectFailure(expect, result, storeFile, 'tests make temp folders with tempDir')
  })

  it('passes mkdtempSync in tests/support/temp-dir and in non-test files', async ({
    expect,
    onTestFinished,
  }) => {
    const allowedFiles = ['tests/support/temp-dir/sample.ts', 'src/shell/release/sample.ts']

    const results = await lintEach(onTestFinished, allowedFiles, mkdtempSyncImport)

    expectEachPass(expect, results, allowedFiles)
  })
})
