# 0003. pnpm as the sole package manager for the frontend

- **Status:** accepted
- **Date:** 2026-06-20
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

The `frontend/` package was scaffolded with npm, and its `package-lock.json` is
the committed lockfile. A partial, uncommitted migration to pnpm already exists
locally (`pnpm-lock.yaml` and a `pnpm-workspace.yaml` declaring
`allowBuilds: sharp, unrs-resolver`). Two lockfiles for one package is a latent
source of drift: installs differ depending on which manager a contributor or
agent happens to run. Which package manager owns the frontend, and how do we
keep that single?

## Decision drivers

- **Install speed and disk usage** — pnpm's content-addressable store hardlinks
  packages, so installs are faster and dependencies are not duplicated on disk.
- **Correctness and supply-chain safety** — pnpm's non-flat `node_modules`
  eliminates phantom dependencies (code can only import what `package.json`
  declares), and the content-addressable store gives integrity guarantees.
- **Tooling coherence (secondary)** — a single declared manager mirrors how the
  Python backend already standardizes on `uv`, removing ambiguity for
  contributors and agents about which command to run.

## Considered options

1. Stay on npm.
2. Adopt pnpm as the sole manager (medium enforcement).
3. Adopt Yarn (Berry / PnP).

## Decision outcome

Chosen option: **pnpm as the sole manager, with medium enforcement**, because it
satisfies all three decision drivers at low cost. "Medium enforcement" means we
pin the manager and make pnpm the default without adding a hard guard that
actively blocks npm.

Concretely:

1. Commit `pnpm-lock.yaml` and `pnpm-workspace.yaml`; delete `package-lock.json`
   and stop tracking it. `pnpm-lock.yaml` becomes the single source of truth.
2. Add `"packageManager": "pnpm@11.3.0"` to `frontend/package.json` so Corepack
   selects pnpm automatically.
3. Do **not** add a `preinstall: only-allow pnpm` guard or an `engines`
   constraint — this is the deliberate boundary of "medium" rather than "strong"
   enforcement, kept for simplicity.
4. Update the **live** documentation that shows `npm …` commands to use
   `pnpm …`: `frontend/README.md` and the "How it runs" section of
   `docs/superpowers/specs/2026-06-16-quaestor-general-design.md`. Historical
   executed plan documents under `docs/superpowers/plans/` are intentionally left
   unchanged — they record what was actually run at the time (including the
   `create-next-app --use-npm` scaffolding) and rewriting them would falsify that
   record.

### Pros and cons of the options

**Stay on npm**
- Good, because zero migration effort.
- Bad, because it forfeits every decision driver and leaves the dual-lockfile
  drift unresolved.

**pnpm (medium enforcement)**
- Good, because it delivers the speed/disk and correctness/safety drivers and
  establishes one lockfile as the source of truth.
- Good, because `packageManager` + Corepack pins the version without per-machine
  setup friction.
- Bad, because each contributor needs pnpm available, and the (future) Docker
  build must be adjusted to use pnpm.

**Yarn (Berry / PnP)**
- Good, because it offers comparable speed and strictness benefits.
- Bad, because Plug'n'Play breaks compatibility with parts of the JS toolchain,
  and the team has no Yarn experience — more risk for no additional gain over
  pnpm.

## Consequences

- Good: reproducible, fast installs with no phantom dependencies, and a single
  lockfile as the source of truth.
- Cost / follow-up — **Docker deploy:** the deploy target is a container, but no
  Dockerfile exists yet. When it is created it must `corepack enable` and run
  `pnpm install --frozen-lockfile`. Tracked here as pending follow-up.
- Cost: every contributor needs pnpm available; Corepack resolves this when
  enabled (`corepack enable`).
- Neutral: there is no CI today, so nothing to migrate there. Any future CI must
  use pnpm (`pnpm install --frozen-lockfile`).

## Confirmation

- `package-lock.json` no longer exists and is no longer tracked by git;
  `pnpm-lock.yaml` is committed.
- `pnpm install --frozen-lockfile` installs cleanly and `pnpm build` compiles.
- `package.json` declares `"packageManager": "pnpm@11.3.0"`.
- Live documentation (README, architecture spec) no longer references
  `npm install` / `npm run` for the frontend.
