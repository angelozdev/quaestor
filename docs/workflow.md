# Workflow

How every feature goes from an idea to something Claude can run against Angelo's
real data.

## From idea to delivery

1. A conversation rethinks the feature from scratch, with no rule inherited from
   the legacy app. It settles what Angelo will ask Claude and what `quaestor`
   must answer.
2. The result is written to `docs/features/<name>.md`: what the feature does, its
   rules, and examples with real numbers. Angelo approves it before anything is
   built.
3. A plan, cut into vertical slices, is written to `docs/plans/<name>.md`. The
   plan lives only while the feature is in progress and is deleted when it is
   done; git keeps it.
4. Each slice is built test-first and delivered on its own.
5. When the last slice is done, the feature's line leaves `backlog.md`, the plan
   is deleted, and `docs/features/<name>.md` describes what was built.

## Slices

- A slice is one behaviour Claude can exercise end to end: a command, its
  validation, the core logic, the store, and the output.
- The thinnest end-to-end slice comes first.
- A slice that delivers no behaviour (shared setup, a pure refactor, a spike) is
  named as an exception in the plan.

## Tests

- Test-first: a failing test, the minimum code that passes, then refactor.
- Tests are of behaviour, never of implementation: a test breaks when what
  `quaestor` does changes, and never when its code is only rearranged. Decided by
  Angelo on 2026-11-24.
- A test checks the resulting state (what is printed, the exit code, what is left
  on disk, what a function returns), never which calls our code made inside
  itself: no spy on an internal function. Fakes stand only for what is outside
  `quaestor`, such as git, pnpm, the bundler or the clock. Decided by Angelo on
  2026-11-25.
- The shell is tested by running the real command through its entry point: it
  asserts what the command prints, its exit code and the files it leaves. No such
  test calls an internal function, reads a table or writes SQL; setup goes
  through commands too. Only code with no command of its own (the release script,
  the lint rules) is tested through its exported function.
- Pure logic in `src/core/` may also be tested directly, through its concept's
  barrel (`#core/<concept>`), for cases the command cannot set up or sets up only
  slowly. Decided by Angelo on 2026-11-25.
- A few end-to-end tests build the release, the same bundle `pnpm release`
  installs, and run it with a temporary home folder. Decided by Angelo on
  2026-11-25.
- Every rule and example in `docs/features/<name>.md` is covered by at least one
  CLI test, and the test's name says which.
- Every money figure has a test in a currency other than COP.
- A rule that must hold for any input also gets a property test with
  `fast-check`, under these practices (decided by Angelo on 2026-11-24):
  - it is a CLI test like any other: `fc.assert(fc.asyncProperty(...))` inside a
    vitest `it` named after the rule, with a fresh store in every run;
  - its oracle is the rule itself (a sum, a balance the export states, the
    positions of the faulty items), never a copy of the code under test;
  - arbitraries are built from fast-check's own and `.map`, with no
    `Math.random` and no `.filter` that drops most values, so shrinking and
    replay keep working;
  - sizes are bounded and `numRuns` is 50, so the suite stays fast;
  - seeds are not fixed; a failure's shrunk counterexample becomes an example
    test named after the rule, before the fix;
  - the spec's examples stay as example tests; properties add the cases no
    example names.
- A test is never weakened, skipped or deleted to make it pass. A test that looks
  wrong goes to Angelo.

## Done

- Tests, lint, format, dead-code and duplication checks are green.
- Claude has run the new commands against a copy of the real data and checked
  balances in cents, not by eye.
- Angelo has merged it and run `pnpm release`.

## Branches and commits

- The trunk is `main`. It grew as the orphan branch `rebuild` until it replaced
  the legacy `main` on 2026-11-25; the legacy app is kept on the local branch
  `legacy`, which shares no history with it.
- Each delivery is built on its own branch and committed after each green step,
  with Conventional Commits in English.
- Claude never commits a delivery's code on the trunk, never merges and never
  pushes. Angelo does.
- Destructive operations (deleting data, removing files git does not track,
  touching the legacy database) are handed to Angelo as commands to run.

## Code

- No code comments. Unclear code is renamed or split until it reads on its own.
- Code, commands, docs and tests in English. Claude speaks Spanish to Angelo.
- Before recommending a library, pattern or tool, Claude checks current industry
  practice instead of relying on memory.
