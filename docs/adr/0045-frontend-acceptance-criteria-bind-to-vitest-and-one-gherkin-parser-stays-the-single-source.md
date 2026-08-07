# 0045. Frontend acceptance criteria bind to vitest, and one Gherkin parser stays the single source

- **Status:** accepted
- **Date:** 2026-08-07
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

Feature 010 (`self-explaining-screens`) is the first feature whose acceptance
criteria live entirely in the browser: 21 ACs about what a screen says, what a
picker offers, what an empty screen teaches, and what a screen reader hears. The
DAE pipeline's Checkpoint 3 formalizes ACs as Gherkin in `spec.md` and generates
runnable tests from them — but every step handler under `acceptance/handlers/`
imports `quaestor.services` and `quaestor.domain` and runs against in-memory
SQLite. There is no browser, no React and no DOM anywhere in that stream.

So of 010's 21 ACs, the generated suite can observe exactly one — AC-18, *"no
figure the app computes changes"* — and 003's existing scenarios already cover
it. Running CP3 unchanged would produce a `spec.md` whose scenarios cannot be
bound to anything.

CHARTER §6 records the same gap from the other side: *"no e2e layer"*. This ADR
decides where a frontend feature's acceptance contract is observed, and what
keeps `spec.md` from becoming prose nobody executes.

## Decision drivers

- **`spec.md` must stay the single contract.** Foundation Design's Checkpoint 3
  requires every AC to map to at least one scenario. A frontend feature that
  quietly stops producing scenarios breaks the checkpoint contract rather than
  extending it.
- **One Gherkin parser.** `dae_gherkin.py` is shipped with the DAE plugin and is
  portable by design — it emits a language-agnostic IR (`.build/spec.json`), not
  Python. A second parser in another language is two things that can disagree
  about the same file.
- **jsdom has no layout engine.** `getBoundingClientRect` returns zero for
  everything, by architecture, in both jsdom and happy-dom. Anything about width,
  overflow or wrapping is unobservable there regardless of which test runner
  wraps it.
- **A real browser is already reachable at zero setup cost.** The agent drives
  Chrome through MCP, and the 2026-08 UX audit used it to find two defects — a
  column falling off a 390px screen, and an unnamed control in the accessibility
  tree — that no test in either suite could have caught. Whatever is decided
  should use that rather than pretend the hole is unavoidable.
- **The repo already writes 44 colocated vitest files** with
  `@testing-library/react`, `user-event` and `jest-dom` — the assertions this
  feature needs are the assertions it already makes.
- **Charter §7 caps the ceiling at the local test surface.** No staging, no
  monitoring, no feature flags. Whatever is decided has to be provable on a
  laptop.

## Considered options

1. **A TypeScript twin of `acceptance/generator.py`** — read the same
   `.build/spec.json`, emit vitest files, write TS step handlers against React
   Testing Library.
2. **Adopt `@amiceli/vitest-cucumber`** — an off-the-shelf Gherkin binder for
   vitest (v7.0.0, published 2026-06-24, 127 releases, actively maintained; an
   RTL template is published alongside it).
3. **Hand-written vitest, with a coverage check against the IR** — `spec.md` and
   `dae_gherkin.py` unchanged; test bodies written as ordinary RTL; a small
   script asserts every scenario name in `.build/spec.json` has a matching test.
4. **Build the e2e layer** — run the same Gherkin against a real browser
   (Playwright or similar), headless and in CI.

Option 3 is what the frontend runner does; **the Chrome MCP is the escape hatch
attached to it** for the scenarios no DOM emulator can see. It is not a fifth
option — it is the answer to option 3's one genuine hole, and it is available
today at zero setup cost because the agent already drives it.

## Decision outcome

Chosen option: **(3) hand-written vitest with a coverage check against the IR**,
because it is the only option that keeps `spec.md` executable *and* adds no
second parser, no second generator and no new dependency — and because 010 is
the first feature to need any of this, so the cheapest thing that preserves the
contract is the right size.

Concretely:

- `spec.md` is written at CP3 exactly as always, and `dae_gherkin.py` produces
  `.build/spec.json` exactly as always. Nothing about Checkpoint 3's front half
  changes.
- The **generated pytest stream is not produced** for a frontend-only feature.
  `acceptance/generator.py` is not taught about React.
- Scenario bodies are **ordinary colocated vitest files**, the same shape as the
  44 that exist, each test named with its scenario name verbatim.
- A **coverage check** reads `.build/spec.json` and the vitest test names and
  fails when a scenario has no test. That check is what makes `spec.md` a
  contract rather than a document — it is the load-bearing half of this
  decision, and without it option 3 collapses into option 4's "prose nobody
  executes".
- **Scenarios jsdom cannot observe are marked `@browser` and verified through
  the Chrome MCP** against the running local stack (`just dev-local`). That is a
  real layout engine, real CSS and the real accessibility tree — the three things
  every jsdom-based option gives up. 010's AC-14 (readable at 390px) is the only
  scenario that needs it today.

  This stream is **agent-driven, not a CI gate**, and the distinction is
  load-bearing rather than a footnote. `pnpm vitest run` and the coverage check
  return an exit code; a Chrome MCP verification returns an observation. A
  `@browser` scenario is claimed green **only** when the checkpoint handoff
  records what was navigated to, at what viewport, and what was observed — the
  same evidence standard every `verified_by: tool` criterion already carries. An
  unrecorded browser check is an unverified scenario.

  The precedent is direct: the 2026-08 UX audit found D10 (the transaction
  amount falling off a 390px screen) and D15 (the accumulate control announcing
  itself as an unnamed checkbox) through exactly this route, and **neither was
  reachable by any test in either suite**.

### Pros and cons of the options

**(1) A TypeScript twin of the generator**
- Good, because it mirrors the backend pattern exactly — one IR, two emitters —
  and every scenario stays machine-generated, so no one can forget to write one.
- Good, because a second frontend feature would cost nothing extra.
- Bad, because it is a large build for a stream with exactly one customer today,
  and the generator plus handlers is the single largest piece of committed test
  infrastructure in the repo.
- Bad, because the step vocabulary a UI needs — *"the screen says"*, *"the picker
  offers"*, *"a screen reader hears"* — has to be invented from nothing, while
  the Python handlers grew out of six features' worth of real steps.

**(2) `@amiceli/vitest-cucumber`**
- Good, because it is maintained and mainstream, and someone else owns the
  binding layer.
- Bad, because it parses `.feature` files, and this repo's contract is `spec.md`.
  Either the spec gets duplicated into a second file, or a second Gherkin parser
  reads the same markdown the Python one reads — and two parsers that disagree
  about one file is a defect with no owner.
- Bad, because it inverts the repo's existing choice: the acceptance pipeline is
  a custom generator over the portable parser, not an off-the-shelf BDD
  framework. Adopting one here would leave the project with both.

**(3) Hand-written vitest with a coverage check** — chosen
- Good, because `spec.md`, `dae_gherkin.py` and the IR are untouched; only the
  *emitter* is skipped for this class of feature.
- Good, because it adds one small script and zero dependencies, and the test
  bodies are the RTL the repo already writes.
- Good, because the check fails loudly on a scenario with no test, which is the
  actual risk being guarded against.
- Bad, because a human writes each binding, so a test can technically carry the
  right name and assert the wrong thing. The generated stream cannot drift that
  way.
- Bad, because it hardens nothing for a hypothetical second frontend feature —
  option 1 stays on the table and gets cheaper to justify each time.

**(4) Build the e2e layer**
- Good, because it is the only option that observes geometry, real CSS and a real
  accessibility tree **and returns an exit code** — the Chrome MCP delivers the
  first three and not the fourth.
- Good, because it would run unattended, in CI, on every push.
- Bad, because it is a project larger than 010 itself, and CHARTER §6 names its
  absence as a known, accepted state rather than an oversight.
- Bad, because it would be decided as a side effect of one copy-and-affordances
  feature, which is the wrong forcing function for the repo's biggest missing
  test layer.
- Bad, because with the Chrome MCP covering the one scenario that needs a real
  browser today, the gap it closes is *automation*, not *coverage* — and the
  automation is worth building when the browser-verified set grows past what a
  human wants to re-check by hand.

## Consequences

- **Good:** Checkpoint 3 keeps its meaning for frontend features — ACs still
  become scenarios, and scenarios still have to run.
- **Good:** No new dependency, no second Gherkin parser, and
  `acceptance/generator.py` stays a backend concern with one job.
- **Good:** The one thing jsdom genuinely cannot see is named explicitly and
  routed to a real browser through the Chrome MCP, instead of being asserted
  falsely against a DOM that reports every element as zero-sized.
- **Good:** The browser stream costs nothing to stand up — the agent already
  drives Chrome, and the local stack is already the charter's validation surface.
  It also reaches things no suite here has ever reached: rendered contrast,
  visible focus, and the accessibility tree as an assistive technology actually
  receives it.
- **Bad / cost:** A scenario can be bound by a test that does not really check
  it. The generated stream makes that impossible; this one relies on review.
  Mitigation is the ordinary one — the ACs are written before the code, and
  Principle 7 keeps the verifier off the implementer.
- **Bad / cost:** `./run-acceptance-tests.sh` no longer covers a whole feature on
  its own. A frontend feature is green only when `pnpm vitest run`, the coverage
  check and every `@browser` scenario all pass, and the feature's `plan.md` Test
  strategy has to say so.
- **Bad / cost:** **`@browser` scenarios do not run unattended.** They need an
  agent, a running local stack and a recorded observation. They cannot gate a
  push, they cannot catch a regression nobody went looking for, and their
  evidence is prose in a handoff rather than an exit code. This is the honest
  price of covering geometry without building option 4, and it is why the
  `@browser` set must stay small — one scenario in 010, and every addition
  argued.
- **Bad / cost:** This defers the e2e question rather than answering it. Two
  triggers for reopening are named: a **second** frontend feature needing bound
  scenarios makes option 1 the cheaper path, and a `@browser` set large enough
  that re-checking it by hand each release stops being reasonable makes option 4
  the cheaper path.

## Confirmation

- The coverage check runs in the same gate as `pnpm vitest run` and fails when a
  scenario in `.build/spec.json` has no test carrying its name **and no
  `@browser` tag**. A tagged scenario is exempt from needing a vitest test and
  subject instead to the evidence rule below; an untagged one with no test fails
  the check. That is what stops `@browser` from becoming a way to skip work.
- **A `@browser` scenario is green only with recorded evidence** in the
  checkpoint handoff: the URL navigated to, the viewport, and what was observed.
  No recorded observation means the scenario is unverified, and the checkpoint
  criterion carrying it is `met: false`.
- Feature 010's `plan.md` Test strategy names all three streams — vitest, the
  coverage check, and the Chrome MCP run — plus 003's existing acceptance suite
  as the proof for AC-18 that no figure moved.
- CHARTER §6's *"no e2e layer"* stands and is now qualified by this ADR rather
  than merely observed: there is no automated e2e layer, and there is a manual
  browser stream with a stated evidence contract.

## Sources

- [@amiceli/vitest-cucumber](https://github.com/amiceli/vitest-cucumber) —
  Gherkin for vitest; [npm registry
  metadata](https://registry.npmjs.org/@amiceli/vitest-cucumber) for the version
  and publish date cited above
- [vitest-cucumber + React Testing Library
  template](https://github.com/Agriculture-Intelligence/vitest-cucumber_rtl_template)
- [Gherkin-style tests with plain Vitest, no extra
  library](https://pearpages.com/blog/2026/06/09/gherkin-style-tests-with-plain-vitest)
  — the 2026 write-up of option 3's shape
- [jsdom — Implement
  getBoundingClientRect](https://github.com/jsdom/jsdom/issues/3621) and
  [happy-dom — getBoundingClientRect always returns
  0](https://github.com/capricorn86/happy-dom/issues/1416) — the missing layout
  engine, in both engines this repo has installed
