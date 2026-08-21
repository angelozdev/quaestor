---
slug: fund-opening-balance
checkpoint: 4
plan_status: confirmed
created: 2026-08-21
---

## Architecture

**Backend — one function changes, one parameter added, no schema change.**

`services/funds.py::set_fund` gains `today: Date | None = None`, the exact
convention already established in this same module family
(`list_recurring`/`restore_recurring` in `services/recurring.py`,
`run_daily` in `jobs/daily.py` — all `X: Date | None = None` defaulting via
`... or Date.today()`). When `balance` is supplied:

```python
if balance is not None:
    fund.anchor_month = year_month_of(today or Date.today())
    fund.anchor_amount = balance
```

replacing today's `fund.anchor_month = None` (the line ADR-041 exists to
fix). `create_fund`/`_validated_spec` — the create-time path — is untouched;
it already dates the anchor to `start_month` correctly.

Neither `FundUpdate` (REST, `api/schemas.py`) nor `SetFundInput` (MCP,
`mcp/tools/funds.py`) gains a `today`/month field. ADR-041 is explicit that
the month is "never chosen freely" by whoever states the balance — exposing
it on either schema would let a caller backdate a statement, exactly what
the decision forbids. Both the REST router and the MCP tool call
`funds.set_fund(session, fund_id, **changes)` exactly as they do today;
`today` simply defaults to the real clock for both. Only the acceptance-test
step handler passes `today=world.today` explicitly, for determinism —
`sinking_funds.py`'s `when_set_fund_balance` (written at CP3, before this
parameter shape was decided) needs that one line added; see Phasing.

**Frontend — one field added to the create-fund form, reusing `MoneyInput`
(feature 018) end to end — no new component.**

- `funds/funds.schema.ts`: `createFundSchema` gains `openingBalance:
  positiveCents.nullable()` — same shape and the same client-side "must be
  positive if given" nicety as the sibling `amount` field already has; no
  `superRefine` entry, since no rule requires it.
- `funds/create-form.tsx`: `defaults()` seeds `openingBalance: null`;
  `bodyOf()` adds `if (values.openingBalance !== null) body.opening_balance
  = values.openingBalance`; a new `<form.Field name="openingBalance">`
  renders `<MoneyInput currency="COP" .../>`, placed right after the
  `startMonth` field (unconditional on `rule` — every rule accepts an
  opening balance per `_validated_spec`), labeled "Ya tiene ahorrado
  (opcional)".
- No table or edit-dialog change (already decided at CP2 — the funds table
  keeps showing the correctly-computed "Tiene" figure; nothing new to
  display).

**Data flow:**

```
Create-fund form (new opening_balance field)
        │
        ▼
POST /funds → create_fund(..., opening_balance=N) → _validated_spec
              (unchanged — already anchors to start_month)

Assistant "set_fund" tool ─┐
REST PATCH /funds/{id}     ─┴─▶ set_fund(..., balance=N, today=None→Date.today())
                                 → anchor_month = year_month_of(today)   [THE FIX]
                                   anchor_amount = N
```

**Key decision.** `today: Date | None = None` on the service function,
never on the public schemas — matches an established, repeated convention in
this codebase and satisfies ADR-041's "never chosen freely" without
inventing a new mechanism.

**Alternative rejected.** A dependency-injected `Clock` abstraction. This
codebase has none anywhere else and already solves the identical
today-vs-testable-today problem four times with a plain optional parameter
— a new abstraction for one function would be unrequested complexity (KISS,
per the project's standing design bar).

**Confirmed with the owner** before drafting the rest of this plan.

## Charter Check

| Charter rule | Status | Note |
|---|---|---|
| §1 Methodology — ADR for architecturally-significant decisions | ✅ N/A | No library/schema/API/auth/testing-strategy/module-boundary decision — a `Date \| None = None` parameter matches 4 existing precedents in this exact codebase, not a new pattern. Product decision (ADR-041) already accepted; this plan implements it. |
| §2 Architecture — layering (`api` → `services` → `domain`) | ✅ | The fix stays entirely inside `services/funds.py`; no new router, no new MCP tool, no schema field crossing the API boundary. |
| §3 Conventions — English identifiers, pnpm, vitest colocated, Zod | ✅ | `today`/`opening_balance`/`openingBalance` are English; `funds.schema.ts` uses the existing Zod v4 primitives (`positiveCents`). |
| §6 Quality stance — foreign-currency case for a money-writing path | ✅, verified not assumed | Traced `fund_status`/`_walk`/`_fold_start`: a fund's own `holds`/`anchor_amount` is reported **in its own currency**, never FX-converted (only cross-fund `overspill` is, per AC-11/ADR-0031) — confirmed by reading `FundFold`'s own docstring and `fold()`'s body. The fix (`anchor_month` dating) touches zero currency-dependent code: it stamps a year-month string and compares it to another year-month string, with no branch on currency anywhere in `set_fund`, `_fold_start`, or the new step handlers. A dedicated USD acceptance scenario would exercise the identical code path under a different label, not a genuinely distinct branch — so one was not added. (Contrast with feature 018, where the currency genuinely changed the formatting logic — not the case here.) `set_fund(balance=...)` is already exercised against USD *charge* funds today by feature 015's existing scenarios (`fund_per_charge.py`'s `given_fund_holds`, for creation/holds display) — this fix does not touch that behavior. |
| §6 Quality stance — green is not verified, browser pass required | ⚠️ → planned | See Test strategy: a manual Chrome MCP pass creating a fund with a stated opening balance is scheduled before CP8 closes, per `feature.md`'s `validation_method`. |
| §7 Autonomy — medium, data gates | ✅ | No schema/migration touch (`anchor_month` already exists, nullable) — nothing here requires escalation past medium. |
| Verification independence (Principle 7) | ✅ | CP6 refine's review subagent(s) are fresh regardless of gating; CP7 verify is dispatched to an agent distinct from the CP5 implementer. |
| Mutation policy (`manifest.mutation`: cadence `on_demand`, `default_per_feature: opt_in`) | **Opt in** | This feature's entire justification is closing 3 real mutation survivors on `_fold_start`'s anchor branch (`stated_for > year_month` inverted, and both its return values) that no scenario has ever pinned. Opting out would defeat the feature's own point. CP8 runs mutation scoped to `services/funds.py`'s changed lines. |

**Amendments:** none. The one ⚠️ row (browser pass) is closed by a planned
step in Test strategy, not a charter exception.

## Phasing

**Two slices — backend fix first (all 5 `@backend` scenarios), frontend
field second (the 1 untagged scenario) — matching the actual dependency: the
frontend field only needs `create_fund`, which is already correct today, so
it does not depend on the backend fix landing first, but sequencing the
already-red backend scenarios first keeps CP5 focused on the one real
behavior change before touching UI.**

1. **`services/funds.py::set_fund`** — add `today: Date | None = None`,
   replace `fund.anchor_month = None` with the dated stamp. Closes AC-3,
   AC-4, AC-5's red scenarios; AC-2, AC-6 stay green (regression-guarded).
2. **`acceptance/handlers/sinking_funds.py::when_set_fund_balance`** — add
   `today=world.today` to the existing `_call(..., "set_fund", ...)`
   invocation (one line; the function already exists from CP3, written
   before this exact parameter was decided).
3. **`funds/funds.schema.ts` + `funds/create-form.tsx`** — the
   `openingBalance` field (AC-1). Independent of slice 1 — could ship in
   either order, but follows it here for focus.
4. **`components/money-input.test.tsx`-style new test** for the create-form,
   or a new/extended `create-form.test.tsx` — binds AC-1's exact scenario
   title, per ADR-0045.
5. Full suite re-run (pytest + vitest), `spec_coverage.py` (6/6 bound),
   CHARTER §6 browser pass.

## Performance budgets

Negligible. One extra optional function parameter (no new query), one extra
form field (no new network round-trip — folded into the existing
`POST /funds` body), one extra `if` branch in an already-loaded fund's
save path. No new indexes, no new N+1, no measurable budget beyond what
`set_fund`/`create_fund` already cost today.

## Collaboration schedule

Solo — CP5 implementer runs directly (small, well-scoped, single real
behavior change plus one form field). CP6 refine and CP7 verify still run as
independent passes per the standard checkpoint contract.

## Execution modes

Local subagent for CP5 implement (auto-dispatched, autonomy `medium`); CP6
refine's review subagent(s) and CP7's independent verifier are also local
subagents. No cloud dispatch (`remote.ready: false`).

## Test strategy

Default DAE stack for the `mixed` acceptance stream (per `feature.md`):
5 `@backend` scenarios (already generated at CP3, 3 green / 2 red for the
right reason) bind to pytest; 1 untagged scenario (AC-1) binds to a vitest
test whose title matches `spec.md` verbatim, per ADR-0045.

**Mutation:** opt in, scoped to `services/funds.py`'s changed lines
(`set_fund` and, transitively, whatever `_fold_start` branches the new
scenarios now exercise). This closes the 3 named survivors on the anchor
branch that motivated ADR-041 in the first place — the acceptance suite
alone proves the *decided* behavior; mutation proves the test suite would
actually catch a regression of it.

**`validation_method` (from `feature.md`):** CHARTER §6 manual browser check
before CP8 closes — create a fund on a COP category via the app, declaring
an opening balance in the new field, and confirm the Funds screen's "Tiene"
column shows the right figure for the current month (not just the generated
suite). The dating fix itself (AC-3/AC-4/AC-5) is a service-layer behavior
with no direct UI to drive in a browser (it is reachable only through the
assistant today, per ADR-041) — the browser pass therefore covers AC-1 and,
incidentally, AC-2 (both observable through the create-fund screen); AC-3/
AC-4/AC-5 stay proven by the acceptance suite plus mutation, which is the
right tool for a fact with no UI surface to click through.
