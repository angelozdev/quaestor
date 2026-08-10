# Quaestor API — what a write needs to get right

Base URL `http://localhost:8000/api`. The token lives in
`backend/.env.local.postgres` as `APP_TOKEN` (gitignored, never print it).

Auth is two independent things and a write needs both:

- `Authorization: Bearer <APP_TOKEN>`
- CSRF double-submit: `X-CSRF-Token: <value>` **and** `Cookie: quaestor_csrf=<same value>`.
  The middleware only compares the two, so any random hex works. Safe methods
  (GET/HEAD/OPTIONS) skip it; everything else gets 403 without it.

`scripts/qapi.py` does both. Reach for raw `xh`/`curl` only for a quick read.

## Contents

- [Endpoints](#endpoints)
- [Payload shapes](#payload-shapes)
- [The rules that refuse](#the-rules-that-refuse)
- [Statuses](#statuses)
- [Transfers](#transfers)
- [What cannot be changed](#what-cannot-be-changed)
- [Traps](#traps)

## Endpoints

| Method | Path | What it does |
| -------- | ------ | -------------- |
| GET | `/accounts` | every account with its balance |
| GET | `/categories` | id, name, direction, exclusion flags |
| GET | `/transactions` | filters: `account_id`, `status`, `date_from`, `date_to`, `category_id`, `type`, `tag`, `sort`, `order` |
| POST | `/transactions` | one expense or income |
| POST | `/transactions/transfer` | a transfer, both legs at once |
| PATCH | `/transactions/{id}` | payee, notes, category, date, tags, meta |
| DELETE | `/transactions/{id}` | removes it, reversing its balance effect if posted |
| POST | `/planned/{id}/confirm` | a planned row becomes posted |
| POST | `/planned/{id}/skip` | cancels that turn (reversible via `/restore`) |
| GET | `/planned/to-pay?since=&until=` | the pending queue |
| GET/POST | `/recurring` | list / create a rule |
| PATCH | `/recurring/{id}` | edit a rule (future occurrences only) |
| GET | `/recurring/{id}/pending-dates` | past dates awaiting a decision |
| POST | `/recurring/{id}/pending-dates/accept` · `/decline` | body `{"due_dates": ["YYYY-MM-DD"]}` |
| POST | `/categories` | create one |
| POST | `/accounts` | create one — `balance` is the opening amount and can only be set here |
| GET/POST | `/funds`, `/funds/preview` | funds; `preview` computes without writing |

## Payload shapes

**Expense or income** — `POST /transactions`

```json
{"type": "expense", "account_id": 5, "amount": 4500000, "currency": "COP",
 "date": "2026-08-08", "payee": "Ana María López", "category_id": 7,
 "notes": "Picada con la familia", "tags": []}
```

`type` is `expense` or `income`. `new_category` creates a category inline but
files it under no group, so prefer creating the category first with a group.

**Transfer** — `POST /transactions/transfer`

```json
{"from_account_id": 4, "to_account_id": 10, "amount": 155604,
 "amount_received": 500000000, "currency": "USD", "date": "2026-08-03",
 "notes": "Préstamo a Ana López Duque"}
```

`amount_received` is required only when the two accounts use different
currencies. Both legs take their `payee` from `notes`, so write the note as the
name you want to see in the list. A transfer carries no category, by design.

**Confirming a planned row** — `POST /planned/{id}/confirm`

```json
{"amount": 21151300, "date": "2026-07-28"}
```

Both optional: omit `amount` to keep the planned figure, omit `date` to keep the
due date. This is the only planned → posted transition, and it moves the balance.

**Recurring rule** — `POST /recurring`

```json
{"name": "Hevy Pro", "payee": "Apple", "type": "expense", "mode": "manual",
 "amount": 3022, "currency": "USD", "category_id": 20, "account_id": 4,
 "interval_unit": "year", "interval_count": 1, "start_date": "2026-07-12"}
```

`mode` is `manual` (creates a planned row to confirm) or `auto` (posts and moves
the balance by itself). `interval_unit` is `day`, `week`, `month` or `year`.

## The rules that refuse

- **Amounts are integer cents.** 45.000 COP is `4500000`. Getting this wrong by
  a factor of 100 is the single most damaging mistake available here.
- **Currency must equal the account's currency** (`recurring.py:112`,
  `transactions.py:97`, `planned.py:78`). A peso amount cannot be written to a
  dollar account. Transfers are the only exception.
- **A category belongs to one direction** (ADR-0042). An income category on an
  expense is refused, and vice versa.
- **Expenses and incomes must carry a category; transfers must not.**
- Amounts must be positive. The sign comes from `type` and, for transfers, from
  the leg's direction.

## Statuses

| Status | Meaning |
| -------- | --------- |
| `posted` | it happened, the balance moved |
| `planned` | expected, no balance movement yet |
| `skipped` | cancelled for good — affects neither balance nor the pending queue |

The owner treats only `posted` as real. Default reads to `--status posted`.

## Transfers

Money that stays in the owner's own accounts is a transfer, never an expense — an
expense would remove it from their net worth and count it as spending. The cases:

- **Paying a credit card**: debit account → card account
- **Lending money**: source account → 🤝 Préstamos a terceros (there is no loan
  feature; this pseudo-account is the agreed workaround). The repayment is the
  same transfer in reverse.
- **Moving to savings or to an internal pocket**: source → the savings account

A credit account's balance follows the same convention as any other: **negative
means debt** (ADR-021), and a payment raises it toward zero. A positive balance on
a card means it was overpaid.

## What cannot be changed

`PATCH /transactions/{id}` accepts payee, notes, category, date, tags and meta —
and nothing else. `amount`, `account`, `currency` and `type` are immutable
because changing them would have to move balances silently.

To correct an amount: `DELETE` then `POST` again. Say so before doing it, because
the movement gets a new id and the old one stops existing.

Deleting one leg of a transfer deletes **both** legs atomically (ADR-0032).

An account's balance cannot be edited at all — only `POST /accounts` sets it, as
the opening amount. After that only movements move it. When a balance is wrong,
the honest fixes are a movement that explains the difference, or a new account
opened at the right figure — not a silent plug.

## Traps

**zsh does not word-split.** `for id in $IDS` passes the whole string as one
value. Iterate line by line:

```bash
while read -r id; do ... ; done < ids.txt
```

**A rule with a past start date offers those dates** instead of charging them
(ADR-0035). If the movements were already recorded by hand, decline the offers or
they stay as phantom pendings. Check `GET /recurring/{id}/pending-dates`.

**Confirming beats creating.** When a planned row exists for a charge, confirming
it keeps one row; creating a new movement leaves the planned one pending forever.

**`just backup` overwrites the day's dump.** Before anything destructive, take one
with its own name (see SKILL.md) so the earlier restore point survives.

**Deleting a planned or skipped row moves no balance**; deleting a posted one
reverses it. Both are fine, but only one changes a number on screen.
