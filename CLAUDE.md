# Quaestor

Before anything else, read `docs/`: `architecture.md`, `stack.md`, `workflow.md` and
`backlog.md`, then the plan in `docs/plans/` if one is in progress, and
`docs/features/<name>.md` for the feature at hand. They are the source of truth and
override this file, which only points at them.

## Commands

- `pnpm quaestor <command>` runs the sources against `data/test.sqlite`; the installed
  `quaestor` is the release and defaults to `prod`.
- `pnpm test` runs the tests; `pnpm check` runs test, lint, format:check, typecheck,
  dead-code and duplication; `pnpm format` fixes formatting.
- `pnpm release` is Angelo's.
