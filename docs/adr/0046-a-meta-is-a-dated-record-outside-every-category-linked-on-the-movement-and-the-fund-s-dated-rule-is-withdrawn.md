# 0046. A meta is a dated record outside every category, linked on the movement, and the fund's dated rule is withdrawn

- **Status:** accepted
- **Date:** 2026-08-08
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

Product side: product ADR-043, which supersedes ADR-037's *"there is no separate
goals feature"* clause and its four-rule list. This ADR is the mechanism.

## Context and problem statement

Feature 009 adds a second noun for planned money. Four days earlier, migration
`0012_the_goal_and_the_envelope_are_gone` dropped `goal`, `goal_contribution`,
`budget` and `transaction.goal_id` on the owner's real database, and its own
docstring says *"the way back is the dump, not the downgrade"*. Anything this
feature builds has to answer why it is not that, undone.

Three constraints shape the answer, all of them already accepted:

- **ADR-0043** stores a fund's rule and derives its balance — *no balance
  column, no account reference* — and folds the month forward over posted
  spending. A meta that stored a balance would be the goal's
  `GoalContribution` ledger returning under a new name.
- **ADR-0044** makes the month a single fold over one bounded aggregate, with
  the identity `income − Σ asks − uncovered = free` holding exactly *so that
  nothing in the breakdown is unattributable*.
- **ADR-0028** caps that read path at a bounded number of statements per month.

And one constraint that arrived from the data. The database was read read-only
on 2026-08-08 with the owner's permission: **`SELECT rule, COUNT(*) FROM fund`
returns zero rows**, 253 of 635 movements are in USD, and `settings.usd_cop` is
a single scalar (`3133.00`), as ADR-0031's amendment requires.

## Decision drivers

- A meta must not reintroduce a stored balance, a savings account, or a monthly
  ritual — the three things ADR-037 deleted.
- The month's identity must keep holding exactly, including in months where the
  owner contributes, cancels or edits.
- The dated fund rule and the meta both mean *an amount by a date*. Shipping
  both is the duplication ADR-037's rejected alternative (A) named.
- The read path's statement count is bounded by ADR-0028 and must stay bounded.

## Considered options

- **(A) A meta is a fund without a category.** Reuses the record, the fold and
  the screen.
- **(B) A meta is its own record, derived like a fund, linked on the movement.**
- **(C) A meta is its own record with a stored running balance.**
- **(D) Keep `target-by-date` and ship the meta beside it**, explaining the
  difference in copy.

## Decision outcome

**Chosen: (B), and (D) rejected — the dated fund rule is withdrawn in the same
feature.**

### The record

`meta` carries a name, an amount, a currency, a target month, a start month, an
optional stated opening amount, and the soft-delete columns ADR-0005 gives every
master. **No balance column and no account reference**, exactly as ADR-0043
constrains the fund.

`meta_contribution` carries a meta, a month and an amount. This *is* the shape
`goal_contribution` had, and the difference is what surrounds it: there is no
ritual that generates rows, no proposal to confirm, and no source account —
product ADR-015's global source account stays dead. A row exists only because
the owner pressed *Aportar*, and he can delete it (AC-42).

`transaction.meta_id` is nullable, and this *is* `transaction.goal_id`
returning. The difference is positional and is the reason the feature works: the
old column hung off a **transfer proposal** that a month-end routine generated
into a forced savings account; the new one hangs off a **posted expense** the
owner names once, on the day he buys the thing. A check constraint refuses it on
anything that is not an expense, mirroring the constraint ADR-036 already put on
`category_id`.

`category.counts_as_saving` is a boolean, default false (AC-41).

### The arithmetic, and the one rule

Everything a meta reports is derived at read time from the fold:

```
ask(M)   = ceil((amount − held entering M) / months from M through the target)
holds(M) = held entering M + ask(M) + contributions dated in M
```

**The month always charges its instalment.** An instalment of zero happens only
because nothing is missing, never because completing, cancelling or editing
waived it. This is the load-bearing rule: without it the money-available
identity and the consumo/ahorro/libre split disagree in every month the owner
acts, which is what the CP3 audits found in the first spec.

Rounding is `_ceil_div` at the cent, the same helper `fund_ask_calc` uses.

### The identity gains two terms

ADR-0044's breakdown becomes:

```
free(M) = income(M) − Σ fund asks(M) − Σ meta asks(M)
                   − contributions(M) + releases(M) − uncovered(M)
```

`contributions(M)` is what the owner set aside by hand; `releases(M)` is what a
cancelled meta gave back. Both are zero in an ordinary month and both are shown
when they are not — ADR-0044's rule that nothing in the breakdown is
unattributable is why they are terms rather than adjustments folded into
another one.

**`uncovered(M)` changes.** A movement carrying a `meta_id` is removed from the
category's spending before the fund's excess is taken, and its own excess —
*spent, less what the meta opened the month with, less what it asks this month*
— is added instead. Every posted expense still counts exactly once, at what left
the account, which is the clause this preserves rather than breaks.

### The read path

The fold gains three queries: the live metas, the contributions dated on or
before the month, and the posted purchases carrying a `meta_id`. **ADR-0028's
bound rises by three statements**, from 10 aggregate loads to 13.

*Corrected during implementation.* This ADR first said two. The third is the
linked purchases, and it is not avoidable: the aggregate's transaction window
holds only the report month and the one before it, while a meta must know
whether it was ever bought — a purchase four months back still completes it.
The row count is bounded by the number of linked purchases, which is at most
one per meta. `test_load_issues_bounded_query_count` is what caught the wrong
figure.

### Currency

A meta is held in its own currency and every figure it reports is in that
currency. Only its peso cost converts, through `to_cop_cents` at the single
scalar TRM — **not** at a per-month rate, which does not exist (ADR-0031,
amended 2026-07-30: *"the TRM is a single scalar value, not a dated series"*,
and the dated `fx_rate` table was dropped in the same migration). With 253 of
635 movements in dollars this is a main path, not a corner.

### The withdrawal

`FundRule.target_by_date` is removed, along with `fund.target_amount` and
`fund.target_month`. The three rules that remain — `fixed`, `average`,
`from_recurring` — are untouched, and a dated **charge** keeps the rule that
fits it: the owner's `Seguro del Carro` and `SOAT carro` are recurring
obligations, and `from-recurring` covers them *and renews itself each cycle*,
which `target-by-date` never did.

## Alternatives rejected

**(A) A meta is a fund without a category.** `Fund` carries
`UniqueConstraint("category_id")` and every read path keys on the category:
`_uncovered` partitions by funded categories, `_ask_average` reads
`spent_in(category_id, month)`, `claim_holdings` attributes to obligations
filed under one. A nullable `category_id` would make each of those branch, and
the one-fund-per-category constraint — 003's AC-25, still live — would need a
partial index to survive. Cheaper in the schema, more expensive in every read.

**(C) A stored running balance.** Simpler to write and it is what
`GoalContribution` did. Rejected because ADR-0043 chose derivation for a stated
reason that has not changed: a stored figure is a second truth that drifts, and
ADR-0044 requires a past month to answer as that month stood. AC-27 is the
behaviour that forbids it, and cancelling in December must not rewrite what
September reported.

**(D) Keep `target-by-date` and explain the difference.** This is the one the
owner reversed himself on, at CP3, after two pieces of evidence. The shipped
label at `frontend/app/(app)/funds/rules.ts:33` reads *"Junto una cantidad para
una fecha"* and its help *"Reparto lo que falta entre los meses que quedan"* —
a meta's definition word for word, reachable only after pressing `+ Nuevo
fondo`, so the owner commits to the noun before the evidence appears. That is
the failure feature 010 existed to fix. And the database says the rule has no
users and no remaining case. Keeping both would have been ADR-037's rejected
alternative (A) — *two ways to depress the same headline* — arriving through
the rule list instead of the noun list.

## Consequences

- **A migration on real data.** One table added, one join table added, two
  columns added (`transaction.meta_id`, `category.counts_as_saving`), two
  dropped (`fund.target_amount`, `fund.target_month`) and one enum value
  removed. Nothing is converted — no fund uses the rule. CHARTER §7 requires the
  owner in person, the manifest caps `backend/src/quaestor/migrations/**` at
  autonomy `low`, and ADR-0030 requires a fresh `just backup` first.
- **ADR-0044 is amended**, not superseded: its fold and its
  everything-adds-up property stand; its breakdown gains two terms and its
  `uncovered` clause gains the meta-netting rule above.
- **ADR-0028's statement bound rises by two.**
- **ADR-0005 is relied on** for the meta's lifecycle. Note it differs from the
  fund deliberately: ADR-0043 hard-deletes a fund because *"an archived fund
  would still have to answer what do you ask this month"*. An archived meta
  answers zero — it asks nothing and holds nothing — so soft-delete is
  available to it where it was not to the fund.
- **A stated deviation from ADR-0006/0009 and CHARTER §2/§4.** The assistant can
  *read* metas — it names them when it explains the money available, because
  otherwise its own breakdown stops reaching its total while 003's AC-10 keeps
  passing at the services layer — but it cannot create, change, contribute to or
  delete one. Write parity is knowingly not met. The owner's reason is that he
  intends to remove the assistant; that removal is its own decision and is not
  taken here.
- **`exclude_from_budget` is untouched by this migration.** It is documented as
  read by nothing since feature 003, but production has it set to true on
  `🔄 Payment / Transfer` — dead in code, live as data. Removing it belongs to
  the doc-drift cleanup, with its own backup, not to this feature.

## Confirmation

`features/009-named-goals/spec.md` — 124 scenarios over 45 ACs, 111 generated
as pytest against the services layer. The two that must stay green throughout
are the pins: *"A fund saving toward a charge still stops the month before,
unchanged"* and *"The three rules that remain are unchanged"*.

The identity is asserted directly rather than inferred: `consumo, ahorro and
libre add up to the income this month` appears in a month with a contribution
and in a month with a cancellation, which are the two the first spec got wrong.
