# Stack

Decided by Angelo on 2026-11-23: the same stack as Aletheia, at the same exact
versions, upgraded together. A dependency enters only with the delivery that
first needs it. There is no ADR folder: when a choice needs its reason written
down, the reason goes next to the choice, in this file or in `architecture.md`.

## Environment

- Node 26.x, ESM.
- pnpm 11.28.8, exact versions saved (`saveExact: true`).
- TypeScript 7.0.2. Development and tests run the sources through Node's native
  type stripping; only the release is bundled.

## Libraries the command uses

All of them are bundled into the release, so they are `devDependencies`.

- `node:sqlite` (built into Node): the data file.
- `drizzle-orm` 1.0.0-rc.5 and `drizzle-kit` 1.0.0-rc.5: tables declared in
  TypeScript, numbered SQL migrations generated from them. Known risk: Drizzle
  1.0 is still a release candidate, as in Aletheia.
- `commander` 15.0.0 with `@commander-js/extra-typings` 15.0.0: commands, flags,
  generated `--help` and `--version`.
- `@toon-format/toon` 4.4.0: output.
- `zod` 4.6.7: validates what enters the CLI and every row imported from the
  legacy export.
- `date-fns` 4.4.0 with `@date-fns/tz` 1.5.0: dates and month boundaries in
  `America/Bogota`.
- `just-*` (one package per utility, for example `just-group-by`): small pure
  helpers. They are wrapped by a single module of our own; nothing else imports a
  `just-*` package, and a lint rule enforces it.

## Development and quality

- `vitest` 5.0.5: tests that run the real command through its entry point.
- `fast-check` 4.10.2: property tests, through the real command, for rules that
  must hold for any input. Aletheia does not use it: Angelo added it on
  2026-11-24. 4.10.2 was the newest release published more than two weeks
  earlier (2026-09-19).
- `oxlint` 1.89.0 with `@oxlint/plugins` 1.89.0 and `eslint-plugin-sonarjs` 4.2.2:
  lint, including the boundary rules in `architecture.md`.
- `oxfmt` 0.74.0: formatting.
- `knip` 6.43.0: dead code.
- `jscpd` 5.4.2: duplicated code.
- `rolldown` 1.2.15: builds the installable release.

## Deliberately absent

- No money library. Amounts are integer cents with one rounding function.
- No Postgres driver. The legacy database is exported once with the `psql`
  already inside its container, and imports read those files.
- No server, web framework, Docker or network calls.
- `ts-fsrs`, which is Aletheia's scheduler and has no place here.
