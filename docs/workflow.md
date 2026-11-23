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
- CLI tests run the real command through its entry point and assert what it
  prints. Unit tests cover the core and the store adapter.
- Every rule and example in `docs/features/<name>.md` is covered by at least one
  CLI test, and the test's name says which.
- Every money figure has a test in a currency other than COP.
- A test is never weakened, skipped or deleted to make it pass. A test that looks
  wrong goes to Angelo.

## Done

- Tests, lint, format, dead-code and duplication checks are green.
- Claude has run the new commands against a copy of the real data and checked
  balances in cents, not by eye.
- Angelo has merged it and run `pnpm release`.

## Branches and commits

- The new project grows on the orphan branch `rebuild`, separate from the legacy
  `main`, until Angelo decides it replaces `main`.
- Each delivery is built on its own branch and committed after each green step,
  with Conventional Commits in English.
- Claude never commits on the trunk, never merges and never pushes. Angelo does.
- Destructive operations (deleting data, removing files git does not track,
  touching the legacy database) are handed to Angelo as commands to run.

## Code

- No code comments. Unclear code is renamed or split until it reads on its own.
- Code, commands, docs and tests in English. Claude speaks Spanish to Angelo.
- Before recommending a library, pattern or tool, Claude checks current industry
  practice instead of relying on memory.
