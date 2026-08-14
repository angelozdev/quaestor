---
skill: crap-analyzer
agent_id: cp7-verifier-independent
feature: 014-fund-explains-what-it-asks
started: 2026-08-12T19:12
ended: 2026-08-12T20:04
checkpoint: 7
artifacts: []
findings_summary: "Every function this branch touched carries 100% line coverage from the two Python streams combined, so no changed function scores above CRAP 5 and the module's worst score, 12.00, belongs to `_validated_spec`, which this branch did not touch. THE FIGURES DID NOT MOVE, AND THAT WAS MEASURED RATHER THAN ARGUED. main's `funds.py` was checked out beside HEAD's and both were driven over 19 fixtures — monthly, yearly, USD, skipped, settled, holdings, over-covering holdings, accumulates-false, average, weekly, every-45-days, every-6-weeks, ends-on-its-last-turn, no obligations, overspent, past anchor, future start — across 21 months, comparing all 16 shared fields of `fund_status`, the same 16 through `fold` plus its overspill, and `preview_fund.would_ask` over every category and both previewable rules. Zero differences. The harness is sensitive: adding one cent to main's divisor produces 837. AC-4 also holds exactly at the service layer, 357 from-recurring readings with `sum(charges.asks) == asks` every time, because the total IS the sum. AC-17 was re-measured independently: `month.available` costs 14 statements at one, five and ten funds. FOUR THINGS CAN STILL PUT A WRONG FIGURE OR A WRONG SENTENCE IN FRONT OF THE OWNER, ALL REPRODUCED. (1) The warning fires quoting `0.00 COP` when the previewed fund already holds the crowded charge's money — driven through POST /api/funds/preview, which accepts `opening_balance`, as does the MCP tool. main warned there too, in its own words, so this is a shape the branch inherited rather than introduced, but AC-11 and AC-12 are new promises and it breaks both. (2) With two crowded charges the warning names the first and quotes only its figure: measured, a fund that would ask 6.500.000 announces 500.000. ADR-0054 moved off the total because the total overstated; naming one of two now understates by the same mechanism, and 🛡️ Auto Insurance is exactly that shape. (3) AC-4 is exact in cents and can be off by one peso on screen, because `formatCents` rounds the row and each line independently — two obligations of 1.000.000 three months out give a row reading $ 666.667 over lines reading $ 333.333 and $ 333.333. Verified against the real formatter with the real service output. (4) A charge whose `end_date` has passed while its rule stays on leaves the fund asking zero forever and showing AC-8's sentence, 'sus cobros están omitidos o ya pagados', where AC-9's is the true one. TWO TEST GAPS WHERE THE GUARD CANNOT FAIL. `has_repeating_charges`, the field that picks between those two sentences, has no backend assertion anywhere: pinning it to False leaves all 1821 Python tests green. And AC-13's seven backend assertions — three scenarios plus the four-row outline — all pass with `preview_fund` monkeypatched to raise on every call, because `then_not_warned` reads a lenient accessor and never calls `require_clean`. That is the vacuous shape CP6 found in 003, now inside 014's own spec, on the criterion ADR-0054 exists for. One dead branch: `_can_be_spread`'s `following is None` disjunct became unreachable when CP6 made it pass `None` as the end date, so line coverage reads 100% over a branch no input can take. Both streams are green: backend 1190, acceptance 631, vitest 546 across 57 files, spec-coverage 33 scenarios and 0 unbound."
human_action_needed: yes
recommended_next: "atdd:mutate for CP8 Harden — agent_id distinct from this one, main-session and cp6-refiner-independent."
tracker_update: "none"
exit_criteria:
  - criterion: "coverage and CRAP were measured over the changed code"
    verified_by: tool
    met: true
    evidence: "pytest-cov and coverage are both absent from the backend venv and nothing was installed; line coverage was taken instead with a stdlib `sys.monitoring` LINE tracer loaded as `-p linecov`, run once over `backend/tests` (1190 passed) and once over `features/*/.build/generated` (631 passed). Combined, `services/funds.py` covers 334/338 executable lines and `domain/dtos.py` 113/115. Every function the diff touched is at 100% line coverage, so CRAP equals its complexity: `_ask_from_obligations` 5.00, `_settled_by_spending` 5.00, `_charge_month_for` 5.00, `_obligations` 4.00, `_status` 4.00, `_crowded` 4.00, `_turn_after` 2.00, `_can_be_spread` 2.00, `_warning` 2.00, `preview_fund` 2.00. The module's worst is `_validated_spec` at 12.00 (complexity 12, 100% covered), untouched by this branch."
  - criterion: "the risk of a wrong figure was assessed against the ACs, not assumed"
    verified_by: inspection
    met: true
    evidence: "main's `funds.py` was loaded beside HEAD's as `quaestor.services.funds_main` and both were driven over 19 fixtures × 21 months, comparing 16 fields of `fund_status`, the same through `fold` plus overspill, and `preview_fund.would_ask` across every category and both previewable rules — 0 differences, against 837 for a one-cent perturbation of main's divisor. `sum(charge.asks) == asks` held over 357 from-recurring readings. `month.available` was counted at 14 statements for 1, 5 and 10 funds. The warning was driven over ten cadences at two start months, over settled and skipped turns, over past and future start months, and through POST /api/funds/preview with an opening balance. `next_due_on_or_after(start, None, …)` was called 252 times across four units, seven counts and three anchors and never returned None."
  - criterion: "every AC is mapped to the stream that covers it, and gaps are named"
    verified_by: inspection
    met: true
    evidence: "All 18 ACs mapped in the table below. Fourteen have real coverage in at least one stream. AC-13's seven @backend assertions survive `preview_fund` raising on every call, so they cannot fail on the criterion they name; AC-8 and AC-9 have no backend assertion at all and their deciding field survives being pinned to False across 1821 Python tests; AC-4 is proved in cents and unproved in pesos, and the one-peso drift is reachable."
  - criterion: "both test streams are green"
    verified_by: tool
    met: true
    evidence: "`./run-acceptance-tests.sh` → 631 passed, 1 warning in 36.69s, exit 0. `cd backend && uv run pytest -q` → 1190 passed, 1 warning in 54.04s. `cd frontend && pnpm vitest run` → 57 files, 546 tests passed. `python3 acceptance/spec_coverage.py features/014-fund-explains-what-it-asks frontend` → scenarios 33, bound to tests 7, @backend 26, unbound 0, exit 0. The working tree is clean; every probe ran from the scratchpad or was deleted after running (`git status --porcelain` empty)."
status: complete
---

## Outcome — applied by main-session on 2026-08-12, owner's selection

The owner chose all five. Every one was reproduced by me before being accepted,
not taken on the report's word.

| | Defect | Fix | Proof |
|---|---|---|---|
| 1 | The announcement named one crowded charge and quoted only its figure — a fund asking 6.500.000 announced 6.000.000. ADR-0054's overstatement, inverted. | `_crowded` returns every crowded charge; the sentence names them all and quotes their sum. | Reproduced before; now reads `Seguro, SOAT … the whole 6500000.00 COP`. Two new `@backend` scenarios. |
| 2 | The screen rounded the row and each line apart, so `$ 666.667` sat over `$ 333.333 + $ 333.333`. AC-4 promises no unnamed remainder. | `sharesAddingTo` in `lib/money.ts` hands the leftover peso to the largest centavos, the way a bill is split. | Reproduced before; three unit tests plus one vitest scenario. |
| 3 | The announcement quoted `0.00 COP` when an opening balance already covered the charge. | A charge asking nothing is not crowded — nothing falls on anyone. | Reproduced; now silent. One new `@backend` scenario. |
| 4 | A rule left on past its end date counted as a charge, so AC-8's sentence showed where AC-9's was true. | `_still_charges` asks whether a turn will actually happen: unskipped this month, or any turn after. | One new `@backend` scenario. |
| 5 | Every AC-13 scenario passed with `preview_fund` raising — `world.attempt` swallowed it, no preview existed, and the absence assertion was vacuously true. | `then_not_warned` requires a preview. 003's `A reachable target is created without a warning` loses the line it never tested, with the owner's permission. | With `preview_fund` raising, 13 scenarios now fail where 0 of the AC-13 ones did. |

### On finding 5, and who caused it

Not the implementer's. **CP6's own correction caused it**: making the shared
accessor lenient kept 003's scenario green and, in the same stroke, made 014's
AC-13 scenarios unable to fail. The right fix was the one CP6 declined to make —
strict step, and 003's vacuous line removed. Two checkpoints to arrive at it,
and it took CP7 running the probe to see it.

### Final state

backend 1190 · frontend 550 · acceptance 634 · lint-imports 2 kept / 0 broken ·
ruff clean · spec-coverage 37 scenarios, 0 unbound. 014 goes 29 → 33 generated
tests.

# CP7 — Light Verify (CRAP + money risk)

Scope: `git diff main...HEAD -- backend/src frontend/app frontend/lib acceptance backend/tests`.
Nothing was fixed. Every claim below was produced by running something.

## 1. How coverage was measured, and what that costs you

`pytest-cov` is not installed in the backend venv and neither is `coverage`;
nothing was installed. Line coverage was taken with a 30-line stdlib
`sys.monitoring` LINE tracer loaded as `-p linecov`, run twice:

| run | tests | what it feeds |
|---|---|---|
| `uv run pytest -q -p linecov` | 1190 passed | the unit column |
| `uv run pytest -q -p linecov ../features/*/.build/generated` | 631 passed | the acceptance column |

**This is line coverage, not branch coverage.** CRAP computed on line coverage
flatters code whose branches are lopsided, and one function in this diff is
exactly that (§4.7). Read the table with that in mind.

**What only the acceptance stream covers.** The unit suite alone leaves
`funds.py` missing lines 494–495 (the `target-by-date` refusal) and 653–657
(`set_fund`'s change branch); the acceptance stream covers all seven. None of
them is in the changed code, so no changed line is acceptance-only. Lines
neither stream reaches: 451 (`_spending_category`'s `NotFound`) and 500–501
(`_rule_of`'s unknown-rule refusal) — both pre-existing. `dtos.py:9` is a
`TYPE_CHECKING` import and never executes.

**`dtos.py` is not really measurable this way.** Its 115 executable lines are
class bodies that run once at import, before any test asserts anything, so its
113/115 says the module was imported, not that anything was checked. It has no
functions but `__str__` (complexity 1), so it contributes no CRAP.

## 2. CRAP over the changed code

`CRAP = comp² × (1 − cov)³ + comp`, complexity by McCabe over the AST, coverage
combined across both Python streams.

| function | new/changed | lines | comp | cov | CRAP |
|---|---|---|---|---|---|
| `_ask_from_obligations` | changed | 14 | 5 | 100% | **5.00** |
| `_settled_by_spending` | changed | 12 | 5 | 100% | **5.00** |
| `_charge_month_for` | changed | 5 | 5 | 100% | **5.00** |
| `_obligations` | changed | 14 | 4 | 100% | 4.00 |
| `_status` | changed | 23 | 4 | 100% | 4.00 |
| `_crowded` | new | 6 | 4 | 100% | 4.00 |
| `_turn_after` | new | 4 | 2 | 100% | 2.00 |
| `_can_be_spread` | new | 2 | 2 | 100% | 2.00 |
| `_warning` | rewritten | 5 | 2 | 100% | 2.00 |
| `preview_fund` | changed | 13 | 2 | 100% | 2.00 |

Worst in the whole module: `_validated_spec`, complexity 12, 100% covered,
**CRAP 12.00** — and this branch did not touch it.

**Is the score earned?** No, and that is the honest reading. Nothing here is
above 5, and 5 is a number CRAP treats as trivial. The scores are earned in the
sense that the lines really do execute — but they are *not* a statement that
the behaviour is checked. §4.4 and §4.6 show two places where 100%-covered
lines carry assertions that cannot fail. CRAP measures execution; it does not
measure whether anyone looked at the result.

## 3. AC-5 — no figure moved. Measured, not argued.

`git show main:backend/src/quaestor/services/funds.py` was loaded beside HEAD's
as `quaestor.services.funds_main` (relative imports resolve, because
`models.py`, `rules.py`, `recurrence.py` and `month_aggregate.py` are untouched
by this branch — confirmed with `git diff --stat`). Both were driven over the
same in-memory database.

**19 fixtures** — monthly COP · yearly COP · yearly USD · mixed monthly+yearly+USD ·
skipped turn · settled by spending · partial holdings · over-covering holdings ·
`fixed` with `accumulates=false` · `average` · fund starting in the future ·
weekly · every 45 days · every 6 weeks · monthly ending on its last turn ·
yearly ending on its last turn · no obligations at all · overspent · anchor in
the past.

**21 months** each (2026-04 … 2027-12). **16 fields** compared:
`fund_id, category_id, name, year_month, rule, asks, holds, spent, carries,
next_month_has, accumulates, accumulation_is_implied, on_track, averaged_over,
spreads_over, whole_by`.

```
== fund_status: 0 differences
== fold: 0 differences          (16 fields per line, plus FundFold.overspill)
== preview.would_ask: 0 differences   (every category × {from-recurring, fixed} × 3 start months)
```

**Negative control, so the zero means something.** Asking main for a different
month makes the harness flag `year_month, asks, holds, carries, next_month_has,
whole_by`. Adding one cent to main's `fund_ask_calc` produces **837**
differences; restoring it returns to 0.

`asks`, `holds`, `carries`, `on_track`, `next_month_has`, `spreads_over` and
`whole_by` all still answer what they answered before this branch.

## 4. Where the money — or the sentence about it — can still be wrong

### 4.1 The warning quotes `0.00 COP` when the fund already holds the money · **defect** · AC-11, AC-12

`_crowded` asks only `can_be_spread and months_to_fund(...) <= 1`. It never asks
whether the charge is still asking for anything. When the previewed fund carries
an opening balance that covers the crowded charge, `would_ask` is 0 and the
warning still fires, quoting zero:

```
would_ask: 0
crowded  : {'name': 'Seguro', 'costs': 600000000, 'charge_month': '2026-09', 'asks': 0, 'can_be_spread': True}
warning  : Seguro charges in 2026-09, which leaves no month to save in: the whole 0.00 COP falls on 2026-08
```

AC-11 says the warning fires only when something cannot be spread; here nothing
is being asked at all. AC-12 says it states *cuánto es*; it states nothing.
The screen would word it as *«los $ 0 caen enteros en agosto de 2026»*.

**Reachable.** `POST /api/funds/preview` takes `FundCreate`, which carries
`opening_balance` (`api/schemas.py:382`), and the MCP `PreviewFundInput`
carries it too (`mcp/tools/funds.py:39`). The funds create form does not send
it, so the browser cannot reach this today — the API and the assistant can.

**Not introduced here.** main warns on the same input in its own words
(`2026-09 leaves no month to save in, so the whole target falls on 2026-08: it
would ask 0 at once`). The shape is inherited; AC-11 and AC-12 are new.

**Reproduction** — drop into `backend/tests/api/`, run, delete:

```python
from tests.support.fx import set_trm as _set_trm


def test_the_preview_warns_about_a_charge_it_says_would_ask_nothing(client, auth):
    _set_trm(client, auth, "4000")
    cat = client.post("/api/categories", json={"name": "Auto", "is_income": False}, headers=auth).json()["id"]
    acc = client.post("/api/accounts", json={"name": "Banco", "type": "debit", "currency": "COP"}, headers=auth).json()["id"]
    client.post("/api/recurring", json={
        "name": "Seguro", "payee": "Seguro", "type": "expense", "mode": "manual",
        "amount": 6_000_000_00, "currency": "COP", "category_id": cat, "account_id": acc,
        "interval_unit": "year", "interval_count": 1, "start_date": "2026-09-02",
    }, headers=auth)
    out = client.post("/api/funds/preview", json={
        "category_id": cat, "rule": "from-recurring",
        "start_month": "2026-08", "opening_balance": 6_000_000_00,
    }, headers=auth).json()
    assert out["would_ask"] == 0
    assert out["warning"] is None, out["warning"]
```

Fails with the warning quoted above.

### 4.2 Two crowded charges: the warning names one and quotes its figure alone · **defect** · AC-12

`_crowded` returns `next(...)` over charges sorted by `charge_month`. When two
charges are both crowded, the owner is told about the smaller one if it sorts
first, and the figure he reads is not the surprise he is about to get:

```
would_ask = 650000000            # $ 6.500.000 falls on 2026-08
crowded   = SOAT, asks 50000000  # $ 500.000
warning   = 'SOAT charges in 2026-09, which leaves no month to save in: the whole 500000.00 COP falls on 2026-08'
```

ADR-0054 stopped quoting the fund's total because the total **overstated** and
frightened the owner off a working feature. Quoting one of two crowded charges
**understates** by the same mechanism — here by a factor of thirteen. The tie is
broken by whatever order `agg.obligations_in` happens to return, so which charge
gets named is not a decision anyone made.

🛡️ Auto Insurance is precisely this shape: SOAT and Seguro del Carro, both
yearly, both under one fund.

**Reproduction:**

```python
c = category(s, "Auto")
obligation(s, c, "SOAT",   500_000_00,   date(2026, 9, 3), unit="year")
obligation(s, c, "Seguro", 6_000_000_00, date(2026, 9, 2), unit="year")
p = funds.preview_fund(s, c, rule="from-recurring", start_month="2026-08")
assert p.would_ask == 650_000_00 * 10 and "6000000.00" in p.warning   # fails: the warning says 500000.00
```

### 4.3 AC-4 is exact in cents and can be one peso off on screen · **defect** · AC-4

At the service layer the lines add up by construction — `_Ask.amount` **is**
`sum(charge.asks)`. Verified over the whole matrix: **357 from-recurring
readings, 0 mismatches.** No rounding hole exists there: `fund_ask_calc` ceils
per obligation and the total is the sum of those same ceils, `claim_holdings`
distributes exactly, and an obligation with `required - taken <= 0` yields
`asks = 0` and still appears as a line, so nothing is dropped and nothing is
unattributed.

The screen is a different story. `formatCents` rounds to whole pesos, and it is
applied to the row and to each line **independently**:

```
backend:  asks = 66666668,  lines = [33333334, 33333334]
screen :  row "Pide" = $ 666.667
          line SOAT  = $ 333.333
          line Seguro= $ 333.333        333.333 + 333.333 = 666.666 ≠ 666.667
```

Produced by two ordinary COP obligations of $1.000.000 three months out — no
dollars needed. Run against the real `lib/money.ts`, on figures the real service
produced.

AC-4 says *«Las líneas suman la cifra del fondo, exactamente»*. Both tests that
guard it use cent-free figures — the @backend one compares integers, and the
vitest one uses 80.000 and 100.000 — so neither can see this.

### 4.4 `has_repeating_charges` decides an owner-facing sentence and nothing checks it · **test gap** · AC-8, AC-9

The field picks between two messages on the funds screen (`page.tsx:161`):

- true → *«Este mes no hay nada que apartar: sus cobros están omitidos o ya pagados.»*
- false → *«La categoría ya no tiene cobros recurrentes … Bórralo, o registra un cobro.»*

Grepped: the only assertions anywhere are frontend fixtures that hand-set the
value. Proof it is unguarded — pin it to `False` for every fund:

```python
# scratch pytest plugin
def pytest_configure(config):
    from quaestor.services import funds
    original = funds._status
    funds._status = lambda agg, fund, walked: dataclasses.replace(
        original(agg, fund, walked), has_repeating_charges=False
    )
```

```
uv run pytest -q -p mutate_hrc ../features/*/.build/generated tests
→ 1821 passed
```

Every Python test stays green while every fund with an empty breakdown tells the
owner to delete it.

### 4.5 An expired charge shows AC-8's sentence where AC-9's is true · **defect** · AC-9

`has_repeating_charges` is `bool(agg.obligations_in(category_id))`, and
`active_recurring` selects on `RecurringItem.active` alone — an `end_date` in the
past does not make an item inactive. So:

```
a category whose only charge ended (end_date 2026-03-05, rule still on)
   asks = 0   charges = []   has_repeating_charges = True
   → the screen says "sus cobros están omitidos o ya pagados"
```

Nothing was skipped and nothing was paid; the charge is over, and the fund will
ask 0 forever — which is the state AC-9 exists to explain. `end_date` is settable
from the recurring screen. AC-9's own case (turning the rule off) works
correctly: `has_repeating_charges` goes False.

### 4.6 AC-13's seven backend assertions cannot fail on their own criterion · **test gap** · AC-13

`then_not_warned` reads `warning_shown`, which is deliberately lenient — it
returns `None` when there is no preview — and it never calls
`world.require_clean`. `World.attempt` swallows exceptions into `world.errors`.
So a preview that *errors* reads as "not warned".

Proof — monkeypatch `funds.preview_fund` to raise on every call:

```
uv run pytest -q -p breakpreview ../features/014-fund-explains-what-it-asks/.build/generated
→ 4 failed, 25 passed
```

The four that fail are the ones that read a figure off the preview. All seven
AC-13 assertions pass:

- `A charge that lands every month is not a surprise`
- `A monthly charge beside a well-spread yearly one is not a surprise either`
- `A monthly charge in its last month is still not a surprise`
- `The four categories that warn today stop warning` × 4 rows

This is the shape CP6 found in 003 (`A reachable target is created without a
warning`), now inside 014's own spec, on the criterion ADR-0054 was written for.
The behaviour itself is right — §4.8 drove it — but AC-13's guard is weaker than
its wording. One `world.require_clean("previewing the fund")` inside
`then_not_warned` closes it; that is a handler change, not mine to make.

### 4.7 `_can_be_spread`'s `following is None` branch is unreachable · **dead code, no defect today**

After CP6's fix the call is `_turn_after(item, charge_month, None)`, and
`next_due_on_or_after` with `end_date=None` cannot return `None` — it increments
`k` until `d >= since`, and `_add_interval` is strictly increasing for
`interval_count >= 1`, which the function itself enforces. Probed across 4 units
× 7 counts × 3 anchors × 3 `since` values: **252 calls, 0 returned None.**

It also always terminates — no non-termination risk from dropping the end date.
The cost is that a genuine one-off is now read by its cadence, which is the
intended behaviour, and that the disjunct is a trap: reinstating the end date
here brings back the exact defect CP6 killed.

Line coverage reads `_can_be_spread` at 100% over a branch nothing can take.
That is the one place in this diff where the CRAP score is an artifact.

### 4.8 Where the warning is right — driven, so it is not an assumption

Ten cadences, charge landing in the start month; and four cadences with the fund
starting the month before the charge:

| cadence | spreadable | warns |
|---|---|---|
| monthly | False | no ✓ AC-13 |
| monthly, ends on this turn | False | no ✓ (CP6's fix holds) |
| weekly | False | no ✓ |
| every 6 weeks | False | no ✓ |
| every 45 days | False | no ✓ |
| every 2 months | True | yes |
| quarterly | True | yes |
| every 90 days | True | yes |
| yearly | True | yes ✓ AC-11 |
| yearly, ends on this turn | True | yes |

Also driven, all correct: a yearly charge this month already **settled by
spending** moves to next year and does not warn; a yearly charge **skipped**
leaves the list, asks 0 and does not warn; a fund starting **2027-04** for a
charge in 2027-06 does not warn while one starting **2027-05** does (003's AC-6,
whole by the month before); a fund whose start month is in the **past** with a
monthly charge does not warn.

### 4.9 AC-10 — currency

Every figure on a `FundCharge` is pesos. `costs = to_cop_cents(item.amount,
item.currency, agg.trm)` and `asks` is derived from that same converted figure
through `fund_ask_calc`; `charge_month` and `can_be_spread` carry no money.
`FundChargeOut` exposes exactly those five fields — there is no raw-currency
field for a USD figure to travel on. Driven at TRM 4000: `30.00 USD` →
`costs = 12000000` cents COP, `asks = 1000000`. AC-15 still refuses the whole
read when no rate is set (`load_month` raises before any charge is built), so no
partial reading escapes.

### 4.10 AC-17 — re-measured, not taken on trust

```
month.available with  1 fund(s): 14 statements
month.available with  5 fund(s): 14 statements
month.available with 10 fund(s): 14 statements
```

Flat. `obligations_in` is an in-memory filter, and the breakdown is the addends
the ask already computed.

### 4.11 One cosmetic note

`page.tsx:181` keys a line by `` `${charge.name}-${charge.charge_month}` ``. Two
recurring charges with the same name in one category, both landing in the same
month, collide. Not money; noted so it is written rather than discovered.

## 5. AC → stream map

| AC | @backend | vitest | verdict |
|---|---|---|---|
| 1 — the figure opens into its charges | `The fund reports one line per charge it is filling for` | `The row carries a line for every charge behind its figure` | covered |
| 2 — cost, month, share | `Each line carries what the charge costs and the month it lands` | `A line says what the charge costs and when it lands` | covered |
| 3 — due vs being saved | two scenarios | `The row separates what leaves this month from what stays` | covered |
| 4 — the lines add up | `The lines add up to what the fund asks` (cents) | `The lines add up to what the row reads` (cent-free figures) | **gap** — exact in cents, one peso off on screen (§4.3), and neither test can see it |
| 5 — no figure moves | two scenarios, 2 data points | — | covered, and independently proved far wider (§3) |
| 6 — a skipped charge leaves the list | `A charge skipped this month is not among the lines` | — | covered |
| 7 — a settled charge leaves, the next turn takes its place | two scenarios | — | covered |
| 8 — a fund asked nothing says so | — | `A fund with every charge skipped explains the empty month` | **gap** — the deciding field is unasserted at the service layer (§4.4) |
| 9 — a category with no charges left says so | — | `A fund left with no obligations at all says the category has none` | **gap** — same field, plus the expired-charge case is wrong (§4.5) |
| 10 — another currency reads in pesos | two scenarios, TRM 4000 and 5000 | — | covered |
| 11 — the warning fires only where nothing can be spread | `A yearly charge landing next month is announced…`, `The owner may create it anyway` | `names the charge and quotes its own figure`, `lets the owner go ahead anyway` | covered for the positive case; **the false positive at §4.1 is untested** |
| 12 — the warning says which charge and how much | `The warning names the charge…`, `The warning quotes the charge, not the whole fund` | same vitest block | covered for one crowded charge; **two crowded charges untested (§4.2)** |
| 13 — a monthly charge never warns | 3 scenarios + 4-row outline | `says nothing when every charge has months to spread over` (real — it waits for `createFund`) | **gap** — all seven @backend assertions pass with `preview_fund` raising (§4.6); the vitest one is the only guard that must fail |
| 14 — the rule is not offered where nothing can be spread | — | two scenarios, plus `falls back to a rule that is still offered` | covered |
| 15 — no rate, same refusal | `A dollar charge with no rate set is refused, not half-read` | — | covered |
| 16 — read, never stored | `The same month read twice at different rates…`, `The records hold no stored breakdown` | — | covered |
| 17 — no extra queries | `Five funds are read in the same number of queries as one` | — | covered, and re-measured (§4.10) |
| 18 — the assistant is not touched | `The assistant reports the figure exactly as it does today`, `The corrected warning reaches the assistant without being asked to` | — | covered; both reds if the assistant answers nothing, so neither is vacuous |

**ACs whose only coverage is a test that cannot fail on its own criterion: 3** —
AC-8 and AC-9 (§4.4), and AC-13 at the backend layer (§4.6, though its single
vitest guard is real).

## 6. What I did not check

- The browser. CP5 drove it; this checkpoint did not re-drive it.
- Mutation testing proper — that is CP8's job. The three targeted mutations here
  (`preview_fund` raising, `has_repeating_charges` pinned, main's divisor
  perturbed) were controls for specific claims, not a survey.
- Frontend line coverage. Only the two Python streams were traced.
