# Spending and income

Status: product and technical part approved by Angelo on 2026-11-25; the plan is in
`docs/plans/spending-and-income.md`.

## Why

Angelo wants to ask Claude free questions about what he has spent and earned, and get
exact figures: how much he spent this year, how much per category, whether he spent more
on restaurants this month than last month, how much he has earned since he started
working, how much his salary went up year by year. `quaestor` computes every figure;
Claude picks the periods to compare and explains what the figures mean.

There is no fixed answer per question. `quaestor` gives spending and income for the
period Claude asks for, by group and by category, so a new question needs no new code
(Claude's call).

## Done when

- Every category belongs to a group, and the misfiled rows below have been moved, each
  shown as a dry run and approved by Angelo, as when recording.
- Claude has answered Angelo's questions with the installed release against the real
  data, with figures checked in cents.

## Not in this feature

How much is available this month, whether something is affordable, budgets, a card's cut
and payment dates, a rate per day or one fetched from outside (such as the official TRM),
loading years before the first recorded movement, what an investment holds (VTI, VXUS,
crypto: in the backlog), a category in more than one group, and splitting one movement
across categories. Also left out (Claude's call): changing a group's kind, which would
change every past answer, unarchiving a category, listing the rates on their own (the
report and `rate set --dry-run` show them), a history of past rates, and a local currency
other than COP.

## What must never happen

- A total that adds two currencies without saying which rate it used.
- A transfer counted as spending or income.
- The same question, at the same rate and with no new movement, giving two answers.
- A change in an investment's value counted as spending or income.

## What counts

- Each group is of one kind: spending, income or outside the totals. A category takes the
  kind of its group, and every category belongs to exactly one group (Claude's call that
  the kind sits on the group). Decided by Angelo on 2026-11-25, as Monarch, Lunch Money
  and PocketSmith do it; deciding by the sign of the amount would count every refund as
  income.
- Spending is the money out of the spending categories, less the money that came back into
  them. Income is the money into the income categories. What is left is income less
  spending (Claude's call, as Monarch and Lunch Money show it).
- A transfer is never spending or income: paying a card, moving money to savings, lending
  to someone. A card purchase is spending on the day of the purchase.
- An opening balance is never spending or income.
- A payment on a debt that has no account in Quaestor, such as a car loan, is spending,
  because it is the only place the purchase shows. Decided by Angelo on 2026-11-25.
- A change in an investment's value is outside the totals and shown in its own line: an
  investment of 25,000.00 USD that falls to 24,000.00 adds no spending, and the answer
  shows "investments: -1,000.00 USD". Interest and dividends that reach an account are
  income. Decided by Angelo on 2026-11-25.

## Refunds

- A refund goes into the category of the purchase and lowers it: 300,000 COP of
  Restaurants in a month with a 50,000 COP refund is 250,000 COP. Decided by Angelo on
  2026-11-25, as YNAB, Copilot, Actual and Rocket Money do it.
- It counts in the month the money arrives, the date the bank shows. Shoes bought for
  200,000 COP on 28 October and refunded on 3 November leave Clothing at +200,000 COP in
  October and -200,000 COP in November; Claude explains the odd month. Decided by Angelo
  on 2026-11-25.
- Someone paying back their share of something Angelo paid is treated as a refund: a
  friend's 600,000 COP share of a 1,200,000 COP rental lowers that category to 600,000 COP
  (Claude's call).

## Currencies

- Every movement stays in its own currency, as recorded.
- An answer gives every total in COP, the local currency, at one fixed rate that Angelo
  configures, and states it: at 4,000 COP per USD, 100.00 USD spent is 400,000 COP. The
  part that was in USD is shown in USD next to it. Decided by Angelo on 2026-11-25.
- One rate for the whole answer means that comparing months shows changes in spending, not
  in the dollar: a 3,000.00 USD salary is worth the same in every month of one answer.
- An answer over a period with any USD and no configured rate is refused, and Claude asks
  Angelo for the rate (Claude's call).

## Periods and views

- A period is any range of days, both included. A month is a calendar month; "this year"
  runs from 1 January to today.
- A month in progress is compared with the same days of the month before: 1 to 25
  November against 1 to 25 October (Claude's call).
- A long period can be split by month, to follow one category or the salary month by month
  (Claude's call).
- Totals come by group, and each group opens into its categories. Decided by Angelo on
  2026-11-25, after seeing one month as 22 category lines and as 12 group lines.
- An answer can be limited to the movements with a tag, or leave them out: "how much did I
  spend on the trip" and "how much did I spend in September without the trip". A trip
  counts as any other spending. Decided by Angelo on 2026-11-25.
- An answer can be limited to one payee: "how much did I spend on Uber this year"
  (Claude's call).
- Answers cover what is recorded. The salary history starts with the first recorded
  movement, and earlier years are not loaded. Decided by Angelo on 2026-11-25.

## Groups

Built by kind of spending, as Monarch, PocketSmith and Lunch Money's detailed set do it;
where they disagree, the placement two of the three use. Approved by Angelo on 2026-11-25.

Spending:

- 🏠 Housing: Rent, Home Maintenance, Laundry
- 💡 Bills & Utilities: Utilities, Services, Internet, Phone
- 🍽️ Food & Dining: Restaurants, Groceries, Food Delivery, Coffee Shops
- 🚗 Auto & Transport: Gas, Parking, Tolls, Car Wash, Car Maintenance, Auto Insurance,
  Rideshare/Taxi, and a new Car Payment
- 🛍️ Shopping: Clothing, Gadgets, Home Goods, Pets
- ⚕️ Health & Wellness: Healthcare, Fitness, Beauty & Wellness
- 🎢 Entertainment: Entertainment, Streaming
- ✈️ Travel: Flights, Car Rental
- 💻 Software & AI: AI Tools, Software
- 🧠 Education: Courses / Learning
- 🎁 Gifts: Gifts
- 🧾 Financial: Taxes, Accountant, Bank Fees

Income:

- 💰 Income: Salary, Bonuses, Interest, Cashback

Outside the totals:

- 🔄 Transfers & Investments: Payment / Transfer, Investment, Investment Gains

Two placements are Claude's call: Software & AI is a group of its own, which none of those
apps ships, because it is one of Angelo's larger monthly lines; Pets goes into Shopping,
because it has one purchase in a year. A new category is created with its group.

Categories the list above does not name, placed by Angelo on 2026-11-25: Food, archived,
goes into 🍽️ Food & Dining; Fun, archived, into 🎢 Entertainment; Refund and Reimbursable
into 🧾 Financial, and both are archived once empty. An archived category that shares a name
with a listed one, such as an archived Auto Insurance, goes into the same group.

No category is ever without a group, not even for a moment. Decided by Angelo on
2026-11-25.

## Moving misfiled rows

- Car loan payments filed under Payment / Transfer move to Car Payment.
- Every row in Refund moves to the category of its purchase. A row there that is not a
  refund becomes what it is, such as a transfer back from the account that holds loans.
- Rows filed under Services that belong elsewhere, such as a utility bill or a rental, move
  to their category.
- Refund and Reimbursable are archived once empty.
- Every move is a correction as `recording-movements.md` defines it: a delete and a new
  record in one `movement write`, shown as a dry run and approved by Angelo. A moved row
  gets a new code and goes to the end of its day. There is no edit command.
- The moves run before the release that brings groups, with the release installed today,
  so Refund arrives empty and its group never touches a figure (Claude's call). Car Payment
  is created then with today's `category add`, and the upgrade puts it in its group by
  name.

## Getting the real data ready

In this order; none of it is code (Claude's call):

1. With the release installed today: create Car Payment and move the misfiled rows above,
   each write a dry run Angelo approves.
2. Before the release, Claude runs the new sources against a copy of `prod`
   (`QUAESTOR_DB`) and checks that the upgrade places every category.
3. Angelo merges and runs `pnpm release`. The first `prod` call backs the store up and
   upgrades it.
4. Claude archives Refund and Reimbursable, and sets the dollar rate Angelo gives.
5. Claude answers Angelo's questions against `prod` and checks the figures in cents.

## The store

- A group has a code, an emoji, an English name and a kind: `spending`, `income` or
  `outside`. Its code is drawn from the same alphabet as every other code. Like every other
  row, it records when it was created, last updated and deleted; a deleted group is marked,
  not removed, and its name can be taken again.
- Every category points to exactly one group, in the store itself: a category without a
  group cannot be written.
- The upgrade that brings groups creates the 14 groups above, in every store, new ones and
  test ones included, and puts every existing category in its group by name, all in one
  step. A store holding a category whose name the list does not know is not upgraded: the
  call fails as `migration_failed` (exit 2) and the store is left as it was, after the
  backup `prod` already takes before any migration. Decided by Angelo on 2026-11-25.
- A rate has a foreign currency and the COP that one unit of it is worth, with at most two
  decimals: 1 USD = 3,912.45 COP. It is stored as integer hundredths of a peso (391245).
  There is at most one rate per currency; setting it again replaces it. COP itself has no
  rate.

## Conversion

- Each movement in a foreign currency is converted on its own, then the converted figures
  are added. 10.85 USD at 3,912.45 is 42,450.0825 COP, rounded to 42,450.08. Decided by
  Angelo on 2026-11-25.
- Every split therefore adds up to the cent: the months add up to the period, the
  categories to their group, and the groups to their line. The USD part times the rate can
  differ from the COP shown by less than one centavo per movement.
- Half a centavo rounds away from zero, through the one rounding function, so a -10.85 USD
  purchase and its +10.85 USD refund convert to exact opposites (Claude's call).
- A figure is exact or the call fails. A two-decimal rate keeps 30,000.00 USD (3,000,000
  cents) times 391245 at 1.2 × 10^12, far below the 15 digits a number prints to the cent;
  a conversion or total beyond 9999999999999.99 exits 2 as `unexpected`, never a figure off
  by a cent (Claude's call).
- The local currency is COP, fixed in code (Claude's call).

## Commands

Codes and dry runs work as in `recording-movements.md`. The output and error codes go in
`docs/architecture.md` and each command's `--help`.

New:

- `quaestor group list`: every group with its code, kind, emoji and name.
- `quaestor group add <name> --emoji <emoji> --kind <kind>`: creates a group, with
  `--dry-run`. A name already taken is `already_exists`.
- `quaestor group edit <code>` with `--name` and `--emoji`, at least one: renames a group or
  changes its emoji, with `--dry-run`.
- `quaestor group delete <code>`: deletes an empty group, with `--dry-run`. A group that still
  holds a category, archived ones included, is refused as `group_not_empty` with its
  `categories`, because no category may be left without a group: to delete 🎁 Gifts, Gifts
  moves to another group first.
- `quaestor category edit <code> --group <code>`: moves a category to another group, with
  `--dry-run`. Its movements count in the new group in every answer, past periods included.
- Creating, renaming and deleting groups and moving a category were added by Angelo on
  2026-11-25. A group's emoji is a field of its own, as a category's is.
- `quaestor category archive <code>`: archives a category, with `--dry-run`. Archiving one
  that still holds movements is allowed: they keep counting in its group, and the category
  takes no new ones (Claude's call).
- `quaestor rate set <currency> <rate>`: sets the rate of a currency, as text with at most
  two decimals and no thousands separator (`"3912.45"`), with `--dry-run`. It shows the
  rate before and after, `null` before when there was none. COP, a rate of zero or less and
  a currency that is not ISO 4217 are refused as `invalid_input`.

  ```
  dryRun: true
  rate:
    currency: USD
    before: null
    after: 3912.45
  ```

- `quaestor report`, below.

Changed:

- `quaestor category add <name> --emoji <emoji> --group <code>`: the group is required.
- `quaestor category list` shows each category's group code.

Removed:

- `quaestor import`, with its code, its tests and its error codes (`already_imported`,
  `export_mismatch`, `balance_mismatch`). It loaded the legacy export into `prod` on
  2026-11-24 and only takes an empty store, so it cannot run there again, and every
  category it wrote would now need a group. The export stays untouched in
  `~/.quaestor/legacy/`; a later feature that needs legacy rows brings its own way in.
  Decided by Angelo on 2026-11-25.

## The report

```
quaestor report --from <day> --to <day> [--by-month] [--tag <tag>] [--without-tag <tag>] [--payee <text>]
```

- `--from` and `--to` are required, both days included; `--to` before `--from` is
  `invalid_input`.
- It counts every live movement with a category in the period. Transfer halves have no
  category, so they never count, and an opening balance is not a movement.
- `--tag` keeps only the movements with that tag; `--without-tag` leaves them out. A tag that
  does not exist is refused as `not_found`, so a misspelt `trip:lima-2062` never answers 0.
- `--payee` keeps the payees containing that text, ignoring case and accents, as
  `movement list` does.
- A period whose counted movements hold a currency with no rate is refused as
  `missing_rate`, with every such `currencies`. A movement the filters leave out needs no
  rate.

Example with invented figures, 1 USD = 4,000 COP, pasted from the real TOON encoder and
approved by Angelo on 2026-11-25:

```
from: 2026-10-01
to: 2026-10-31
currency: COP
rates[1]{currency,rate}:
  USD,4000
totals[4]{line,total,USD}:
  income,12015000.5,3000
  spending,2130000,20
  left,9885000.5,2980
  outside,-4000000,-1000
groups[5]{id,kind,emoji,name,total,USD}:
  k2m9,income,💰,Income,12015000.5,3000
  p4w8,spending,🚗,Auto & Transport,1200000,0
  h7d3,spending,🍽️,Food & Dining,850000,0
  r6t1,spending,💻,Software & AI,80000,20
  x3n5,outside,🔄,Transfers & Investments,-4000000,-1000
categories[7]{id,group,emoji,name,total,USD}:
  c3d4,k2m9,💰,Interest,15000.5,0
  a1b2,k2m9,💼,Salary,12000000,3000
  j9k0,p4w8,🚘,Car Payment,1200000,0
  g7h8,h7d3,🛒,Groceries,600000,0
  e5f6,h7d3,🍽️,Restaurants,250000,0
  m1n2,r6t1,🤖,AI Tools,80000,20
  q3r4,x3n5,📈,Investment,-4000000,-1000
```

The rows above were reordered on 2026-11-25 to follow the order below, and `code` became
`id` as every list names it; the figures are the ones Angelo approved.

- `total` is in COP. Each foreign currency in the counted movements adds a column named by
  its code, with the part that was in that currency, in that currency; a period all in COP
  has no such column and `rates: []`.
- Spending is positive and a refund lowers it. Income is positive. What is outside the totals
  keeps the movement's sign: the investment fell 1,000.00 USD.
- `totals` always has its four lines: income, spending, left (income less spending, in every
  column) and outside. `groups` and `categories` list only those with counted movements.
- Groups come by kind (income, spending, outside), then by name; categories follow their
  group, then by name, and two with the same name by code (Claude's call).
- `--by-month` adds a first `month` column (`2026-10`) to the three tables. Months are
  calendar months cut to the period, and every month in it has its four `totals` lines, a
  month with no movement at 0, so a month without salary shows as 0.

  ```
  totals[3]{month,line,total,USD}:
    2026-09,income,12000000,3000
    2026-09,spending,1900000,15
    2026-10,income,12015000.5,3000
  ```

- The refusals, each exit 1:

  ```
  error:
    code: missing_rate
    currencies[1]: USD
    message: no rate for USD; set one with quaestor rate set
  ```

  ```
  error:
    code: not_found
    kind: tag
    value: "trip:lima-2062"
    message: "tag trip:lima-2062 does not exist"
  ```

  `not_found` also answers a group or category code that does not exist in `category add`,
  `category edit`, `category archive`, `group edit` and `group delete`.

## The skill

- A new skill in `.claude/skills/spending-and-income/`, which calls the installed
  `quaestor`, never `pnpm quaestor`, as `record-movements` does (Claude's call).
- It holds Claude's judgment, never a sum: which periods to ask for ("this year" is 1
  January to today; a month in progress against the same days of the month before), when to
  split by month, when to filter by tag or payee, how to explain an odd month such as a
  refund landing after its purchase, and stating the rate in every answer.
- On `missing_rate` Claude asks Angelo for the rate, shows `rate set --dry-run`, and sets it
  after his yes.

## Tests

- As `workflow.md` sets them: CLI tests through the entry point, each named after the rule
  or example it covers, with setup through commands.
- The upgrade is tested from a store at the previous migrations that holds categories with
  movements, one of them archived and sharing a name: every category lands in its group, and
  an unknown name fails the upgrade and leaves the store as it was. No command can build
  that store, so the test loads a readable text file of invented rows right after the
  previous migrations and before the new one; everything after goes through commands.
  Decided by Angelo on 2026-11-25, as the one exception in `workflow.md`.
- "Every money figure has a test in a currency other than COP" means, for the report, its
  foreign part: the conversion and the foreign columns are tested in USD and in KRW, each
  with its own rate. The `total` column is always COP, the local currency (Claude's call).
- A property test, oracle the rules themselves, for any movements: the months add up to the
  period, the categories to their group, the groups to their line; left is income less
  spending; each converted figure is the sum of its movements converted one by one; and a
  transfer never changes the report.

## Approaches

Product choices, made on 2026-11-25 after reviewing the help centers of YNAB, Monarch,
Copilot, Actual Budget, Lunch Money, Rocket Money and PocketSmith:

- **What is spending**: by the category's group, chosen; by the sign of the amount, as
  PocketSmith does by default, dropped because a refund would count as income.
- **Currencies**: one total in COP, chosen; one total per currency, dropped because months
  could only be compared currency by currency and spending could not be set against the
  USD salary. Only Lunch Money and PocketSmith convert, each with a rate per day.
- **The rate**: one fixed rate Angelo configures, chosen; the official rate of each
  movement's day, and the rate of Angelo's own conversions, dropped for now; today's rate
  for every answer, left for later.
- **Refunds**: lower the purchase's category, chosen; a line of their own, dropped because
  comparing a category month by month would include money that came back. In the month the
  money arrives, chosen; in the purchase's month, dropped because a closed month would
  change after the fact.
- **Groups**: saved groups, chosen; Claude picking categories per question, dropped because
  two conversations could add up "food" differently.
- **Trips**: counted as any spending with a tag filter, chosen; always apart, dropped
  because the year's total would leave the trip out.

Technical choices, made on 2026-11-25:

- **Existing categories**: the upgrade puts each in its group by name, chosen by Angelo;
  a report that refuses or sets apart a category with no group, dropped by Angelo because no
  category may be without one; two releases, the first leaving groups for Claude to fill
  and the second making them required, dropped because categories would sit without a group
  in between.
- **The rate's precision**: two decimals with each movement converted, chosen by Angelo; a
  whole-number rate, dropped because a currency worth a few pesos (1 KRW ≈ 2.9 COP) could
  not be written; two decimals with each total converted, dropped because the months would
  not add up to the year.
- **The report's output**: flat tables joined by codes, chosen by Angelo; groups holding
  their categories, dropped because by month it nests three levels and runs about twice as
  long.
- **`import`**: retired, chosen by Angelo; kept, placing each legacy category by the same
  name list, dropped because the list would live twice and drift.
- **Moving rows**: today's `movement write`, chosen because a correction is a delete and a
  new record (decided on 2026-11-24); an edit command, dropped for the same reason.
- **Claude's calls**: a skill, chosen because picking periods and explaining figures is
  judgment; only the command's `--help`, dropped because it cannot hold how Claude answers.
