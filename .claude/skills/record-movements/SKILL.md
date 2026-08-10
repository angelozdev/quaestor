---
name: record-movements
description: Record real bank movements into Quaestor's production database through the local API, from screenshots of a banking app or a dictated list. Use whenever the owner wants to log, enter, catch up or annotate transactions in any account — Nu Débito, DolarApp, RappiCard, Nu Crédito, Emergency Fund, Korea, Préstamos a terceros, DolarApp Earnings, DolarApp Invest — or says things like "anotar mis cuentas", "registrar movimientos", "meter estas transacciones", "poner al día la cuenta", "agregar unos gastos", "ya pagué esto", or simply sends a screenshot of a bank statement. Also use when asked what the last movements of an account are, since that reading is the first step of the same job.
---

# Recording movements into Quaestor

The owner reads the bank app and Quaestor does not. Closing that gap is this job:
turn what the bank shows into movements in the production database, without
duplicating what is already there and without inventing what was never said.

**Everything here writes to real financial data.** The database is the local
Postgres container (ADR-0030), it holds actual money, and there is no undo button.
That is why the shape of this work is: read a lot, ask a little, show what you are
about to do, write only after the owner says yes.

All output to the owner is in **Spanish**. The API contract, the field rules and
the traps live in `references/api.md` — read it before your first write of a
session, and whenever something refuses.

## The helper script

`scripts/qapi.py` handles the token and the CSRF pair, which is where hand-rolled
calls go wrong. Prefer it over raw curl:

```bash
python3 .claude/skills/record-movements/scripts/qapi.py context
python3 .claude/skills/record-movements/scripts/qapi.py movements 5 --status posted --limit 10
python3 .claude/skills/record-movements/scripts/qapi.py precedents "uber" "exito"
python3 .claude/skills/record-movements/scripts/qapi.py batch /tmp/movimientos.json
```

`xh` is installed if you want a one-off call by hand, but remember a write needs
`Authorization`, `X-CSRF-Token` and a `Cookie` carrying the same token value.

## Before anything

1. Confirm the stack is up and pointed at production:
   `docker ps` should show `quaestor-db-1`, and the api container's `QUAESTOR_DB`
   should say `db:5432`. If it is not running, say so — do not start it silently.
2. Run `qapi.py context` once. Accounts, categories and recurring rules in one
   read. You will need all three, and guessing a category id is how wrong data
   gets written.

## The workflow

### 1. Read what is already there

Before touching a screenshot, look at the account's recent movements:

```bash
python3 .claude/skills/record-movements/scripts/qapi.py movements <id> --status posted --limit 5
```

**Posted only, unless asked otherwise.** The owner has said plainly that planned
rows are not real movements and should not be counted as such. Presenting a
`planned` row as if it had happened costs them a correction.

This read also tells you the last date Quaestor knows about, which is the line
between "already registered" and "new".

### 2. Transcribe the screenshots

Screenshots overlap — scrolling and capturing means the same rows appear twice.
Order everything chronologically and deduplicate before presenting anything.

Three things in a statement are not movements to record:
- rows marked **Anulada** — the charge was reversed, it never happened
- a **card payment** already registered as a transfer (check before assuming)
- anything **already in the database** from a previous session

Rows marked **Pendiente** are a judgement call: they will almost certainly settle,
so ask whether to record them now rather than deciding alone.

### 3. Decide what each row is

This is the part that distinguishes a good pass from a mess. For each row, work
out which of these it is:

| It is… | What to do |
|--------|-----------|
| already in the database | leave it out, and say so in the summary |
| the real charge of a **planned** row | `POST /planned/{id}/confirm` with the real amount and date — never create a second movement |
| money between the owner's own accounts | a **transfer**, not an expense (see `references/api.md`) |
| genuinely new | `POST /transactions` |

Finding the planned twin matters more than it sounds: a card payment, the rent or
a subscription usually has a planned row waiting, and creating a new movement
beside it leaves a phantom pending forever. Compare by amount and by rough date,
not by exact date — the bank charges when it charges.

### 4. Work out the category before asking

`qapi.py precedents "<payee>"` shows how that payee was categorised before, with
counts. If there is a clear precedent, follow it — the owner named these
categories, and consistency is worth more than your opinion about where a charge
belongs.

Ask only about what history cannot answer: an unknown merchant, an ambiguous one,
or a purpose that changes the category (a transfer to a person could be a dinner,
a loan, or a contribution to a savings goal — the amount will not tell you).

"I do not remember" is a fine answer: record it with a note saying so. That has
been the owner's own choice before, rather than leaving a hole.

### 5. Show before you write

Summarise what you are about to do, with the numbers the owner will recognise:

- the operation and the affected account
- amount in pesos or dollars as the owner says them, never in cents
- category and note
- **the balance before and after**

The balance projection is the most valuable line, because it is the thing that can
be checked against the bank app in one glance — and it is how a wrong assumption
gets caught before it is written rather than after.

Then get confirmation. For a handful of movements, one at a time. For a long
list, offer to confirm **by group** (all the Ubers, all the parking) and let the
owner choose — twenty-six individual confirmations for near-identical rows is a
worse experience than three.

### 6. Write, then verify

Write with `qapi.py batch` for a group, or `call` for a single operation. Then
read the balance back and compare it to what you projected. If it does not match,
stop and investigate before continuing — a mismatch means something else moved,
and it is far cheaper to find out now.

Report with ids, so any row can be found later.

## When the numbers do not add up

Sooner or later a balance will not match the bank. That is information, not an
obstacle: it usually means movements are missing, and the gap is the size of what
was never registered. Investigate before proposing a fix — reconstruct the
account from its movements, compare against what the bank app shows, and explain
what you found in the owner's terms. Never plug a difference silently.

Anything destructive — deleting rows, adjusting a balance, bulk edits — takes a
backup first, with its own dated filename:

```bash
docker exec -i quaestor-db-1 sh -c 'pg_dump -U "${POSTGRES_USER:-quaestor}" --format=custom --no-owner "${POSTGRES_DB:-quaestor}"' \
  > "$HOME/Library/Mobile Documents/com~apple~CloudDocs/QuaestorBackups/quaestor-pre-<que-vas-a-hacer>-$(date +%F).dump"
```

Use a distinctive name rather than `just backup`, which overwrites the day's dump
and would destroy the restore point from before the session.

## Recurring charges

A repeating charge often deserves a rule so it stops being manual. Before creating
one, check `context` — it may already exist with a stale amount, which is more
common than it missing entirely. Prices drift, and a rule quietly wrong is worse
than no rule.

A rule with a start date in the past **offers** those dates for a decision instead
of charging them (ADR-0035). If those movements were already recorded by hand,
decline the offers or they linger as phantom pendings. Check
`GET /recurring/{id}/pending-dates` after creating one.

## Things that get noticed if you get them wrong

- **Cents.** Every amount in the API is integer cents. The owner speaks in pesos.
- **A credit card in debt has a negative balance** (ADR-021). Positive means the
  card was overpaid, not that there is money in it.
- **A movement inherits its account's currency.** A COP amount cannot be written
  to DolarApp; only a transfer accepts two currencies.
- **Amount and account are immutable.** Correcting either means deleting and
  recreating, which changes the id — say so before doing it, not after.
