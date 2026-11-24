# Recording movements

## Why

Angelo reads his bank apps; Quaestor does not. Every question he will ask later (how
much he spent last month, how much he has available, whether a trip fits) needs every
bank movement in Quaestor: in its account, at its real value, categorised and tagged,
with each account's balance equal to what the bank shows. This feature brings the
legacy data over and lets Claude keep it up to date from bank screenshots.

## Done when

- The legacy export is imported, and every account's balance equals its
  legacy stored balance to the cent.
- Claude has recorded a real movement from a bank screenshot with the installed
  release: a dry run first, then the write after Angelo says yes.

## Not in this feature

Budgets, repeating charges and planned rows, metas, funds, the dollar rate, spending
reports, category groups and category flags, any behaviour tied to an account type
(such as a card's cut and payment dates), archiving an account,
splitting one charge across categories, the time of day, editing a movement in place,
duplicate detection in code, the original foreign amount as data, any total across
currencies, and measuring TOON against JSON in tokens: TOON stays the output whatever
the result, so Angelo dropped the measurement on 2026-11-24.

## What must never happen

- A balance made to match the bank with an unexplained adjustment.
- A movement recorded from an app's activity list that no bank statement shows.
- A write Angelo has not seen as a dry run and approved. The skill enforces this, not
  `quaestor`, which cannot see Angelo's yes; writes keep a plain `--dry-run` (Claude's
  call).

## A recording session

The skill drives it; `quaestor` answers.

1. Angelo sends screenshots.
2. Claude reads the account's balance and recent movements, to know what is already
   there.
3. Claude transcribes the screenshots, drops overlap and what is already recorded, and
   proposes each row's category and tags from how that payee was categorised before.
4. Claude asks only what it cannot infer, one question per message.
5. Claude shows the dry run: each movement, and each touched account's balance before
   and after.
6. Angelo says yes, and Claude writes.
7. Claude compares the final balance with the bank's. If they differ, Claude helps
   Angelo find the cause, and once it is found it is recorded as a real movement with
   its category (bank interest, a refund, whatever it was). Decided by Angelo on
   2026-11-24.

## Codes

Accounts, categories and movements are each identified by a random four-character code from
`0123456789abcdefghjkmnpqrstvwxyz`, as Aletheia's cards are: `n8d3`, `k7f2`. They are never
numbered in sequence. A code already taken is drawn again, so two never share one, and
1,048,576 fit in each list: more than a lifetime of movements. Decided by Angelo on
2026-11-24.

## Accounts

- An account has an emoji, a name, a type, a currency, an archived mark and an opening
  balance.
- The emoji is a field of its own, one emoji such as 🏦, and the name is plain text such as
  Bank. Categories work the same way. Decided by Angelo on 2026-11-24.
- The type is `savings`, `debit`, `credit` or `cash`. Nothing depends on it yet: a later
  feature gives credit accounts their cut and payment dates. Decided by Angelo on
  2026-11-24.
- A currency is any ISO 4217 code; anything else, such as `UDS`, is refused.
- The balance is the opening balance plus the sum of the account's movements. It is
  always computed and never stored, so it cannot drift the way Card C's did when it
  was reset by hand.
- A credit card in debt has a negative balance: Card B is at -1,000,000.00 COP.
- An archived account receives no new movement. Card A and Trip fund arrive archived.
- A new account is created with its emoji, name, type, currency, and opening balance and date,
  the opening balance being 0 when the account starts empty.

## Opening balance

The money an account held before its first recorded movement. It is neither income nor
expense, so it never counts in what Angelo spent or earned. Each account has at most
one, and the account's running balance starts from it. A movement dated before its
account's opening date is refused (Claude's call, so a running balance never starts
mid-history).

Some legacy accounts get one, dated the day before their first posted movement. Decided
by Angelo on 2026-11-24:

- 🆘 Reserve: +5,000,000.00 COP on 2026-03-01.
- 📈 Invest: +1,000.00 USD on 2026-07-01.
- 💵 Wallet: +500.00 USD on 2026-01-05.
- 🏦 Bank: +1,200,000.00 COP on 2026-01-05.
- 💳 Card C: -300,000.00 COP on 2026-01-05. The difference really comes from the
  hand reset of 2026-08-01, so the balance today is exact and the balances before that
  date are not.
- 💳 Card A: -2,000,000.00 COP on 2026-02-01. Its origin is unknown; today's
  balance, 0, is exact.

## Amounts and currencies

- An amount is an integer in its currency's minor unit, as ISO 4217 defines it: COP
  45,000.50 is `4500050`, USD 10.85 is `1085`, KRW 15,000 is `15000`.
- It is signed: positive is money into the account, negative is money out. Zero is
  refused (Claude's call).
- A movement is always in its account's currency. A purchase made in another currency
  is recorded as what the account was charged: the 500 MXN tacos paid with Wallet
  are -30.39 USD on Wallet. The original amount goes in the note when Angelo wants
  it. Decided by Angelo on 2026-11-24.
- Nothing converts between currencies, and nothing adds two currencies together.

## Movements

- A movement has an account, a date, a payee, an amount, a category, zero or more tags
  and an optional note. The payee and the category are required.
- The date is the calendar day the bank shows, with no time. Movements on the same day
  keep the order in which they were recorded. Decided by Angelo on 2026-11-24, when he
  dropped the time of day: it can be added later as optional, and every earlier
  movement would then simply have none.
- Any category takes money in or money out. A 20.00 refund from Rappi on a 50.00 order
  can go into 📦 Food Delivery, leaving delivery at 30.00 for the month. Decided by
  Angelo on 2026-11-24, as YNAB, Actual Budget and Rocket Money recommend.
- One bank charge is one movement with one category (Claude's call).
- Accounts, categories, tags and movements record when they were created, last updated and
  deleted, as UTC instants. A deleted movement is marked, not removed: it leaves every list
  and balance but stays stored. Decided by Angelo on 2026-11-24.
- A correction is a delete and a new record in the same write: the movement gets a new
  code, and nothing refers to the old one. Decided by Angelo on 2026-11-24.

## Transfers

- A transfer moves money between two different accounts of Angelo's. It is two linked
  halves, one in each account, each with its own amount in its own currency, its own
  date, its own payee and its own note. It has no category. Decided by Angelo on
  2026-11-24 over double-entry bookkeeping (see Approaches).
- Both halves are written together or not at all, and deleting one half deletes both.
- Paying a card, moving money to the Reserve and lending to someone (through 🤝
  Loans) are transfers.
- A transfer across currencies carries both amounts: -100.00 USD from Wallet, +400,000.00
  COP into Bank. `quaestor` does not compare them, because it knows no rate. Both are
  shown side by side so Claude can check the rate they imply against the statement
  (Claude's call: no rate is computed).
- Each half having its own date is Claude's call: a transfer can leave one bank on the
  10th and reach the other on the 11th, and each statement shows its own date. All 48
  legacy pairs share a date.

## Categories and tags

- A category has an emoji, an English name and an archived mark: 🍽️ and Restaurants. A tag has a name such
  as `trip:lima-2026` or `who:alex`.
- An unknown category or tag is refused. Creating one is a separate write with its own
  dry run, so a misspelt `trip:lima-2062` never slips in. Decided by Angelo on
  2026-11-24.
- An archived category receives no new movement.
- Tags can go on any movement, transfer halves included (Claude's call). The legacy data
  has none on transfers.

## What Claude can ask `quaestor`

Reads:

1. The accounts, with each one's balance today.
2. Movements, filtered by account, by a date range and by payee text. For one account,
   each movement comes with the account's balance after it, so Claude can check against
   a statement ("on 31 October Bank showed 1,500,000.00"). The payee filter is how Claude
   finds how a payee was categorised before.
3. The categories and the tags.

Writes, each with `--dry-run`:

4. One write that records movements and transfers and deletes movements, any number of
   each, all or nothing. Its dry run shows each change, and each touched account's
   balance before and after.
5. Create a tag; create a category.
6. Create an account.
7. Import the legacy export, once.

## Importing the legacy export

- It reads `~/.quaestor/legacy/`, checks every file's row count and sha256 against
  `manifest.json`, and validates every row with zod before writing anything.
- It refuses a store that already holds data, so nothing is imported twice.
- Every account, category and movement gets a new code; the legacy numbers are not kept.
- What comes over:
  - every account, some of them archived, each with its legacy type: `debit` (Wallet, Bank), `credit` (Card A, Card C, Loan, Card B), `savings` (Reserve, Trip fund, Earnings, Invest) and `cash` (Loans).
  - every category, some of them archived, with
    no posted movement in an archived one. Their groups and flags stay in the export
    for the reports feature.
  - Each legacy name splits into its leading emoji and the rest: 🏦 Bank becomes 🏦
    and Bank. A name without an emoji keeps none.
  - every tag.
  - every posted movement: expenses, incomes and both halves of every transfer.
  - every tag link, all on posted movements.
- Signs: an expense becomes money out and an income money in, a transfer's `out` half
  becomes money out and its `in_` half money in. A negative expense, which the legacy app used for money coming back, therefore becomes money in, as it was.
- What stays in the export: the skipped and planned rows, the links to metas and to repeating rules, and `source`. Movements keep their legacy `created_at`.
- The six opening balances above are added. After the import every account's balance
  equals its `manifest.json` balance to the cent; if any differs, nothing is written.
- Claude runs it on a copy of the real data first, then on `prod`.

## The skill

- `record-movements` lives in `.claude/skills/record-movements/`, so it works only with
  Claude open in this repo. It calls the installed `quaestor`, never `pnpm quaestor`.
  Decided by Angelo on 2026-11-24, knowing that a half-finished skill on a branch could
  ask the release for a command it does not have yet.
- It follows the session above: one question per message; only a bank statement creates
  a movement, and an app's activity list only helps label one; a row the bank marks as
  pending is asked about, not decided.

## Approaches

How a movement is stored:

- **Two linked halves**, as YNAB and Actual Budget do: a transfer is one row in each
  account, linked; an expense or income is one row. Chosen by Angelo on 2026-11-24.
- **Double-entry**, as Beancount, Ledger and GnuCash do: every movement is two or more
  lines summing to zero, with categories acting as accounts. It guarantees money never
  appears or vanishes, but its extra guarantee only matters for transfers, which the
  linked halves already write together or not at all, and the rest serves formal
  accounting nobody asked for.

Trimmed from the first proposal on 2026-11-24, at Angelo's agreement: editing in place,
duplicate warnings in the dry run, a separate "how was this payee categorised" command,
archiving an account, the time of day, and account types. Angelo brought account types
back the same day, for the credit-card behaviour he plans.

## Changes to `architecture.md`

- Money: an amount is an integer in its currency's ISO 4217 minor unit, not always
  cents.
- Legacy data: the difference between a stored balance and its movements is carried as
  the account's opening balance.
- Skills: `record-movements` lives in `.claude/skills/` and calls the installed
  `quaestor`.

## Left to the builder

- Command names, flags, input shape on stdin, output fields, and how Claude refers to an
  account, a category or a movement. Two categories share the name Gifts,
  one of them archived.
- The tables and how the opening balance is stored.
- The order of the slices.
