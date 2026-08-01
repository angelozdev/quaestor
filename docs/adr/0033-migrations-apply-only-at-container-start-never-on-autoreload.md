# 0033. Migrations apply only at container start, never on autoreload

- **Status:** accepted
- **Date:** 2026-07-31
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

Twice on 2026-07-31, an Alembic revision was applied to Angelo's real financial
database with no human running a command — 0006 at 15:27Z and 0007 at 22:05Z,
both before the runbook's backup step
(`features/002-transactions-crud/runbook.md`). Writing a migration file into
the working tree while `just dev-prod` is up **is** running it in production.
The operational rule written after the first incident ("bring the pg stack down
before touching `migrations/`") did not prevent the second, because it relied on
a human remembering. What structural change makes the auto-apply impossible
rather than merely discouraged?

The mechanism is more specific than the runbook recorded. There are **two**
independent migration triggers, not one:

1. `__main__.run_migrations()` — a subprocess `alembic upgrade head`, run once
   per container start. This is ADR-0026's "wait, migrate, serve" entrypoint
   contract, kept in force by ADR-0030. It is human-initiated by `just dev-prod`.
2. `api._lifespan` → `db.init_db()` → `db._apply_migrations()` →
   `alembic_command.upgrade(cfg, "head")` — run on **every FastAPI application
   start**. Uvicorn runs with `reload=True, reload_dirs=["/app/src"]`
   (`__main__._run_uvicorn`) and compose bind-mounts `./backend/src:/app/src:rw`,
   so every file an agent writes under `backend/src` restarts the app process
   and re-runs this. Container logs confirm the ordering: the
   `alembic.runtime.migration` lines appear after `WatchFiles detected changes …
   Reloading` and before `api: lifespan startup`, which is `db.init_db(db.engine)`
   at `api/__init__.py:35` executing before the log line at `:36`.

Trigger 2 is the incident mechanism, and it is an undocumented duplicate of
trigger 1 — no ADR ever decided that migrations should run on autoreload.

## Decision drivers

- **The data is irreplaceable.** A local Postgres container holds the user's
  real finances (ADR-0030). An unattended, unbacked-up schema write is the worst
  failure mode this project has.
- **Two occurrences, one root cause.** A rule that depends on human memory has
  already failed twice; the fix must remove the mechanism.
- **Do not break the accepted bootstrap contract.** ADR-0026 decided
  wait-migrate-serve and ADR-0030 explicitly kept it. A fix must not silently
  contradict that.
- **Do not break the test path.** `db.init_db()` is how every test fixture
  builds its schema (`tests/conftest.py`, `tests/api/conftest.py`,
  `tests/mcp/conftest.py`, `tests/chat/conftest.py`), and
  `tests/api/test_startup.py` deliberately pins that `uvicorn quaestor.api:app`
  serves a fresh DB with no manual `init_db` step.
- **Agents write files as a matter of course.** Any workflow where an agent
  edits `backend/src` must be safe by construction, not by a checklist.

## Considered options

1. **Stop bind-mounting `backend/src` in the pg profile** — compose only.
1b. **Invert the default: no `src` bind mount in the base `api` service; a
   `docker-compose.dev.yml` override restores it, and only `just dev-local`
   passes that override** — compose only.
2. **Gate migrations behind `QUAESTOR_AUTO_MIGRATE`, off for the pg profile** —
   code + env.
3. **Pre-flight refusal: `just dev-prod` aborts when revisions are pending.**
4. **Keep the operational rule and write it louder.**
5. **Combination: 1b + 3.**

## Decision outcome

Chosen option: **5 — invert the bind-mount default so hot-reload is opt-in to
the sqlite sandbox alone, plus a pre-flight check that refuses to start
`dev-prod` while revisions are pending.**

Removing the mount deletes the mechanism behind both incidents: with no bind
mount there is no WatchFiles event, so trigger 2 can never fire against real
data. It is a compose-only change, contradicts no ADR, and losing hot-reload
against the production database is a feature, not a cost — code should be edited
against the sqlite sandbox. Option 3 then covers what remains: trigger 1 is
legitimate and human-initiated, but it should announce a pending schema change
and demand a backup rather than apply it silently. Together they turn "a file
write migrates production" into "a human sees `2 pending revisions — run just
backup, then just migrate`".

**1b is chosen over 1** (decision amended before acceptance, 2026-07-31). The
`api` service declares no `profiles:` key, so it runs under every profile with
one shared volume list; "remove the mount from the pg profile" would mean
splitting `api` into two near-duplicate services. Inverting the default is a
smaller change and a safer one: the dangerous configuration becomes the thing a
recipe must explicitly ask for. It also covers `dev-real`, which carries the
same mount against the Render standby and which option 1 left armed.

Option 2 is deliberately **not** chosen as the primary. It works, but it edits
the shared `db._apply_migrations` choke point that every test fixture depends
on, so it risks the test path to fix a deployment problem, and it leaves the
bind mount — meaning a future profile change silently re-arms the gun.

### Pros and cons of the options

**1. No `src` bind mount in the pg profile**
- Good, because it removes the reload trigger entirely instead of guarding it.
- Good, because it is compose-only: no application code, no test surface.
- Good, because it preserves ADR-0026's entrypoint contract untouched.
- Bad, because backend code changes need a container rebuild in that profile.
- Bad, because `api` has no `profiles:` key, so scoping the volume list per
  profile requires duplicating the service.
- Bad, because `dev-real` keeps the mount.

**1b. Invert the default; `docker-compose.dev.yml` restores the mount**
- Good, for every reason option 1 is good.
- Good, because one volume list stays in one place — no duplicated service.
- Good, because it covers `dev-prod` and `dev-real` in the same edit.
- Good, because a profile added later inherits the safe default.
- Bad, because `just dev-local` grows a second `-f` flag, so invoking compose by
  hand without it silently loses hot-reload.

**2. `QUAESTOR_AUTO_MIGRATE` env gate**
- Good, because it is explicit and greppable, and covers both triggers.
- Bad, because `_apply_migrations` is on every test fixture's path; a default
  that is wrong in tests turns 750 green tests red for a deploy-side reason.
- Bad, because the bind mount survives, so the mechanism is only masked.

**3. Pre-flight refusal on pending revisions**
- Good, because it converts a silent write into a visible, backed-up decision.
- Good, because it also catches the legitimate `just dev-prod` path.
- Bad, because it adds a step to a recipe Angelo runs often.

**4. Operational rule only**
- Good, because it is free.
- Bad, because it is the status quo and it has already failed twice.

## Consequences

- Good: writing a migration file while the pg stack is up becomes inert.
- Good: schema changes against real data become explicit and backup-gated.
- Good: the ADR-0026/0030 bootstrap contract is restored rather than weakened —
  trigger 2 was never a decision, just an accident of `init_db` doing two jobs.
- Good: `dev-real` is covered by the same change, so the Render standby stops
  carrying a live migration trigger.
- Bad / cost: editing backend code under `dev-prod` or `dev-real` needs a
  rebuild; hot-reload survives only in the sqlite sandbox.
- Bad / cost: `db.init_db()` keeps conflating "apply migrations" with "seed and
  wire hooks". Splitting those is the follow-up this ADR does not take on.

## Confirmation

- A test asserting the base `api` service declares no `./backend/src` volume
  (parse `docker-compose.yml`), and that `docker-compose.dev.yml` restores it.
- The pre-flight check is itself the runtime confirmation: `just dev-prod` exits
  non-zero and names the pending revisions when `alembic heads` is ahead of the
  database's `alembic_version`.
- `features/002-transactions-crud/runbook.md` records both incidents and is the
  regression story this ADR answers; a third occurrence means this decision
  failed.
