# 0047. The module boundaries are enforced, the dead code and the copies are reported

- **Status:** accepted
- **Date:** 2026-08-09
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

Feature 009 ended with a dependency direction worth keeping — `month` folds above
`funds` and `metas`, and those two no longer know each other (ADR-0046, commit
`61fa014`) — held up by nothing but a docstring. A single `from . import metas`
inside `funds.py` puts the coupling back and no gate says a word.

The frontend does not have that problem. `biome.json` already refuses an import
from `ui/` into `@/app`, `@/lib`, `@/components` or `@/hooks`, which is ADR-0002
written as a lint error rather than a convention. The backend has no equivalent:
`ruff.toml` selects seventeen rule families and `TID` is not among them.

Two smaller gaps came out of the same review. Checkpoint 8's mutation sweep found
`_Month.contributed` — a field written in three places and read in none — after
an hour of mutation, because a dead field is the one thing a mutation score
cannot tell apart from an untested one. And `dae_dup.py`, which the Refine
checkpoint runs before dispatching its Reuse reviewer, returns
`status: unavailable` on this machine, so that reviewer works from model judgment
alone every time.

## Decision drivers

- **A boundary that only a document defends is not defended.** ADR-0046's
  dependency direction is the load-bearing outcome of 009 and it is currently
  unprotected.
- **Prevention beats reporting.** A tool that fails the build the day a rule is
  broken is worth more than one that lists what already accumulated.
- **Measure before adopting.** The standing bar is DRY, low coupling, high
  cohesion, KISS. A tool that reports noise costs attention and buys nothing.
- **Token cost is a real cost.** Work a deterministic tool can do should not be
  paid for in model judgment on every Refine checkpoint.
- **Metrics that do not predict anything are not worth wiring in.** Cyclomatic
  complexity predicts perceived understandability with around 30% error;
  Cognitive Complexity did not outperform the metrics it was built to replace;
  the Maintainability Index is inflated by comment volume, which this project
  bans outright, and overweights lines of code.

## Considered options

1. **Nothing.** Keep the boundary as a docstring and let the Reuse reviewer
   judge duplication.
2. **`import-linter` only.** Close the one structural gap and stop.
3. **`import-linter` + `knip` + `jscpd`.** Enforce the boundary; report dead code
   and copies.
4. **Add a complexity gate too** — Cognitive Complexity or the Maintainability
   Index over the changed diff.
5. **`dependency-cruiser` and `vulture` as well**, for full symmetry across both
   halves.

## Decision outcome

Chosen option: **`import-linter` + `knip` + `jscpd`** — option 3 — because it
takes the one boundary that is genuinely unprotected and makes it a gate, and
adds only the two reporters that were measured to produce signal on this
codebase rather than noise.

Options 4 and 5 were rejected on evidence gathered before deciding, which is
recorded below because the evidence is the whole reason.

### Pros and cons of the options

**Nothing**
- Good, because it costs no dependency and no runtime.
- Bad, because the coupling 009 spent a refactor removing can return silently,
  and the Reuse lens keeps paying model tokens for a job a tokenizer does.

**`import-linter` only**
- Good, because it is the entire structural gap, in two contracts.
- Bad, because it leaves the dead exports where they are — and one of them,
  `listContributions` / `removeContribution`, has been on the outstanding list
  since Checkpoint 5.

**`import-linter` + `knip` + `jscpd`** — chosen
- Good, because the boundary becomes a gate and the two reporters were each run
  against this repo before being adopted: `knip` returned 2 unused files, 11
  unused exports and 16 unused types with its one noise class configured away;
  `jscpd` returned 43 clones at 1.99% over source, including the four CRUD
  screens that share most of their shape.
- Good, because `jscpd` turns `dae_dup.py` from `unavailable` into `ok`, which
  is the token saving the owner asked for by name.
- Bad, because it is three more dev dependencies and one machine-local shim.

**A complexity gate**
- Bad, because the published validation does not support it. Cyclomatic
  complexity was a *modest* predictor of understandability in a 216-developer
  study and not of problem severity; a 2023 study puts prediction error near
  30%. Cognitive Complexity validates against comprehension time but did not
  beat the earlier metrics in comparison. The Maintainability Index rewards
  comment volume, which CLAUDE.md prohibits project-wide, so it would score this
  project worse for following its own rule.
- Bad, because Checkpoint 7 already computes CRAP over the changed diff, and it
  returned zero backend findings above threshold while the residue underneath it
  — eleven lines no test stream reaches — was the thing actually worth knowing.

**`dependency-cruiser` and `vulture`**
- Bad, because measured. `vulture --min-confidence 80` over `backend/src`
  returns **one** finding and it is a false positive (a `Protocol` method's
  parameter); at 60 it returns **179 lines**, almost all of them Alembic's
  `revision` / `down_revision` module globals and FastAPI route handlers that
  nothing statically "calls". FastAPI, SQLModel and Alembic are exactly the
  dynamic dispatch it cannot see.
- Bad, because `dependency-cruiser`'s marginal value over the Biome rule already
  in place is circular-dependency and orphan detection; `knip` reports orphans,
  and a Python backend is outside its reach entirely.

## Consequences

- **Two import contracts, in `backend/pyproject.toml`.** The first is the
  package layering — `api` above `chat` above `mcp | jobs` above `services`
  above `domain`. The second is 009's seam:

  ```
  quaestor.services.month
  quaestor.services.funds | quaestor.services.metas
  quaestor.services.month_aggregate
  ```

  `|` means the two are independent: neither may import the other. That is
  ADR-0046's outcome expressed as a check rather than as prose.
- **`just lint` gains `lint-imports`.** It runs against the whole package, not a
  diff, so the contracts hold for every commit rather than for the reviewed one.
- **`just dead` and `just dup` are reports and never gates.** A dead export is a
  decision about the product — `listContributions` is dead because the
  contributions history was never built, and the answer might be to build it —
  and duplication below the threshold of a real abstraction is cheaper left
  alone. Neither belongs in a check that blocks a commit.
- **One calibration for duplication, not two.** `.jscpd.json` at the repo root
  carries the formats and the ignores; `jscpd` reads it on its own, so `just dup`
  and `dae_dup.py` answer with the same 43 findings instead of drifting. Tests,
  `acceptance/`, and the generated `.build/` trees are excluded: with them in,
  161 of 204 clones were test arrange-blocks, which are deliberate and drowned
  the rest.
- **`knip` needs `ui/index.ts` declared as an entry point.** ADR-0002 makes
  `ui/` an app-agnostic design system, so a component it exports that no screen
  has used yet is intended, not dead. Without that line, 35 of 56 reported
  exports were that barrel. `shadcn` and `tw-animate-css` are ignored as
  dependencies for the reason `app/globals.css` already states: their CSS is
  vendored into `ui/styles/`, and the packages are kept to pin the version it
  was vendored from.
- **A machine-local shim, and it is not in the repo.** `dae_dup.py` invokes the
  literal command `jscpd`, so the tool has to be on `PATH`; pnpm's global bin
  directory is not on this machine's. `~/.local/bin/jscpd` is a two-line wrapper
  that execs `frontend/node_modules/.bin/jscpd`, which keeps the version pinned
  to the lockfile. If it is missing or dangling, `dae_dup.py` degrades to
  `status: unavailable` exactly as it did before — nothing breaks.
- **Cost: three dev dependencies** (`import-linter` in the backend group,
  `knip` and `jscpd` in the frontend's) and roughly two seconds added to
  `just lint`.
- **Findings this decision surfaced and did not act on**, left for the owner:
  `components/phase2-banner.tsx` and `lib/utils.ts` are unused files — and
  `lib/utils.ts` justifies itself in a comment claiming shadcn's `@/lib/utils`
  alias needs it, while `components.json` points that alias at `@/ui/lib/cn`;
  `metas.schema.ts` exports `metaContributionSchema` and three `*Values` types
  that nothing imports, all written during 009's Checkpoint 6 and missed by its
  Reuse reviewer.

## Confirmation

`cd backend && uv run lint-imports` → `Contracts: 2 kept, 0 broken`, over 83
files and 249 dependencies. Both contracts were falsified before being trusted:

- adding `from . import metas` to `funds.py` breaks the seam contract with
  `quaestor.services.funds is not allowed to import quaestor.services.metas`,
  naming the line;
- adding `from ..api import errors` to `services/accounts.py` breaks the layering
  contract with `quaestor.services is not allowed to import quaestor.api`.

Both files were restored and `git status` verified clean afterwards.

`python3 …/dae_dup.py .` → `status: ok`, 43 duplicates, where it returned
`status: unavailable` during feature 009's Checkpoint 6.
