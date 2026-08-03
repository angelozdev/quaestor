# 0040. Strict ruff lint as a gate on the acceptance pipeline

- **Status:** accepted
- **Date:** 2026-08-02
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

Nothing lints Python in this project. There is no `[tool.ruff]` in
`backend/pyproject.toml`, no ruff in `[dependency-groups]`, no entry in
`uv.lock`, no `ruff.toml`, no lint recipe in the `justfile`, no CI and no
pre-commit hook — `uv run ruff check --version` fails with "No such file or
directory". The frontend has had Biome enforcing its equivalent since P6, so
the two halves of the codebase are held to different standards.

The gap surfaced during feature 007's review. Vestigial `# noqa: E402,F401`
and `# noqa: BLE001` directives were found suppressing rules for a linter that
never runs, and the same review round caught prohibited code comments that the
implementer's own accounting had missed three separate times — twice
undercounting, once naming the wrong file. Every one of those was mechanically
detectable. The owner does not write Python and cannot review it, so the
absence of a linter is not a stylistic gap; it removes the only reviewer that
does not get tired.

## Decision drivers

- The owner cannot self-review Python. The tool has to be the reviewer, which
  argues for strictness over convenience and for a gate over an honour system.
- `CLAUDE.md` bans code comments project-wide. `# noqa` **is** a comment, so
  every suppression must be expressible in configuration; a rule set that can
  only be lived with via inline escapes is disqualified.
- The Python surface spans `backend/` **and** the root-level `acceptance/`
  package, so the configuration cannot live in `backend/pyproject.toml` alone.
- A rule that fires on correct, idiomatic code trains the reader to ignore
  output. Precision matters more than coverage.
- Measured, not assumed: 27,047 lines across 214 files; line lengths p50 32,
  p95 81, max 147.

## Considered options

1. **Strict, tuned to this stack** — a curated `select` covering correctness,
   security and modernization, with stack-specific false positives excluded.
2. **Ruff's built-in defaults** — no `select` at all.
3. **`select = ["ALL"]`** — everything ruff ships.
4. **Start minimal (F + E) and add families over time.**

Measured against the tree at `c55fab2`:

| Option | Violations | Auto-fixable |
|---|---|---|
| 1. Strict, tuned | **444** | 276 |
| 2. Built-in defaults | 464 | 310 |
| 3. `ALL` | 10,012 | 1,303 |
| 4. Minimal (F + E) | ~50 | most |

## Decision outcome

Chosen option: **1, strict tuned to this stack**, wired as a **blocking gate on
`run-acceptance-tests.sh`** plus a standalone `just lint` recipe.

Configuration lives in a **root-level `ruff.toml`**, because `acceptance/` sits
outside `backend/` and a single invocation must cover both.

```toml
line-length = 120

[lint]
select = [
    "F", "E", "W", "I", "UP", "B", "C4", "T20", "PIE", "RET", "SIM",
    "PTH", "PERF", "LOG", "RUF", "ISC", "A", "INT", "PGH", "ERA",
    "S", "ASYNC", "BLE", "SLF", "TRY", "PLE", "PLW", "PLC",
]
ignore = ["B008", "TRY003", "RUF012"]
```

`line-length = 120` because only 10 lines in the tree exceed it, against 119 at
100 — the stricter number would buy a reformat of the whole codebase for no
readability gain at p95 = 81.

The four blanket `ignore`s each correspond to a construct this stack makes
correct:

- **B008** function-call-in-default-argument — FastAPI's `Depends()` idiom; 61
  hits, all correct code.
- **TRY003** long messages outside the exception class — the codebase's errors
  deliberately name the offending id and value, which is what makes a refusal
  actionable (see ADR-029 in `product-decisions.md`).
- **RUF012** mutable class default — collides with SQLModel/Pydantic field
  declarations.

**PLC0415** (import-outside-top-level) was in this list in the first draft and
was pulled out at the owner's instruction: *imports always go at the top*. The
measurement supports them. Of 240 hits, only 14 are in production source, and
only five of those — all in `services/bootstrap.py` — are load-bearing: that
module imports inside functions precisely so `transactions.py` never learns
what a recurring item is (see its module docstring). The other nine are
artefacts with no rationale at all — `import json` inside `_json_dumps`,
`import logging` inside a config reader, `from datetime import date` inside two
MCP tools. Those move to the top; `bootstrap.py` keeps a per-file ignore, and
tests keep one because fixtures import lazily by convention.

Two families were considered and rejected as noise rather than signal:
**DTZ** (36 hits on `date.today()`, which is deliberate here — every service
takes a `today` override so the boundary is testable) and **TC** (98 hits
demanding imports move into `TYPE_CHECKING` blocks, pure churn).

Per-file ignores carry the rest, so no `# noqa` is ever needed:

```toml
[lint.per-file-ignores]
"backend/tests/**" = ["S101", "SLF001", "ERA001", "PLW", "PLC0415"]
"acceptance/**"    = ["S101", "SLF001", "ERA001", "PLW", "BLE001", "PLC0415"]
"backend/src/quaestor/services/bootstrap.py" = ["PLC0415"]
"backend/src/quaestor/migrations/**" = ["ERA001"]
```

`RUF100` (unused-noqa) is inside the selected `RUF` family, so a leftover
suppression is itself reported — the configuration polices its own escape
hatch.

### Pros and cons of the options

**1. Strict, tuned**
- Good, because it catches the classes of defect that actually occurred here:
  dead code, blind `except`, forgotten commented-out code (`ERA`), leftover
  `print` (`T20`), and hardcoded secrets (`S`).
- Good, because every suppression is expressible in config, satisfying the
  no-comments rule.
- Bad, because the exclusion list is a judgement that needs revisiting when the
  stack changes; a wrong exclusion hides real findings silently.

**2. Built-in defaults**
- Good, because it needs no justification and drifts with upstream.
- Bad, because it admits 97 known false positives (B008, DTZ) that train the
  reader to skim, and omits `S`, `ERA`, `T20` and `PTH` — families that map
  directly onto real risk here.

**3. `ALL`**
- Bad, because 1,648 of the 10,012 hits are `assert` in tests, which is how
  tests are written. Unusable without an exclusion list larger than option 1's.

**4. Minimal, escalating**
- Good, because it lands today with no sweep.
- Bad, because "we'll tighten it later" is the failure mode this decision
  exists to prevent, and the sweep only grows.

## Consequences

- Good: a mechanical reviewer for the half of the codebase its owner cannot
  read, enforced rather than optional.
- Good: the gate makes zero-violation the resting state of `main`, so the sweep
  is paid once instead of compounding.
- Cost: a one-time sweep of 444 violations before the gate can be switched on —
  276 auto-fixable, the rest by hand.
- Cost: `run-acceptance-tests.sh` gains a failure mode unrelated to behaviour.
  A lint error will now stop the tests from running at all, which is the point,
  but it means a red pipeline no longer implies a broken feature.
- Surfaced by the measurement: 10 `assert` statements in production code.
  `assert` is deleted outright under `python -O`, so an assert is a check that
  can vanish. Nothing in this repo runs with `-O` (no `PYTHONOPTIMIZE`, no `-O`
  in the Dockerfile or any recipe), so this is a dormant trap rather than a live
  defect. Reviewed individually: the eight in `chat/events.py` narrow a type for
  the checker (`assert event.tool_call_id is not None`) and stay. The two in
  `chat/mcp/client.py` guard a real usage contract — without them the caller
  gets `AttributeError: 'NoneType' object has no attribute 'list_tools'` instead
  of "use `async with MCPClient(...)`" — so they become `raise RuntimeError`,
  which cannot be optimized away.
- **`ruff format` is in scope**, and so is formatting the whole frontend with
  Biome. The first draft of this ADR recommended the opposite — deferring the
  formatter because adopting it rewrites the entire tree in one diff, as
  happened earlier in this session when `biome check --write .` reformatted 26
  untouched frontend files and had to be reverted. The owner overruled it
  directly: *both halves must always be fully formatted, and reformatting a
  file nobody touched is fine.* That is the stronger position — the earlier
  revert treated a large diff as the problem when the real problem was that the
  tree was never formatted in the first place, so any formatting run looks like
  a rewrite. Paying it once ends the recurrence. Formatting lands as its own
  commit, separate from the lint fixes, so the behavioural diff stays readable.

## Confirmation

`run-acceptance-tests.sh` runs `ruff check` before generating or running any
test and aborts non-zero on violations, so the decision is self-enforcing: it
cannot regress without the acceptance suite going red. `just lint` runs the
same check on demand. Both invoke ruff from the repo root against the single
`ruff.toml`, covering `backend/` and `acceptance/` together.
