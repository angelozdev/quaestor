# Spending and income

Status: product approved by Angelo on 2026-11-25; the technical part (commands, store,
output) is still to be settled.

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
across categories.

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

## Moving misfiled rows

- Car loan payments filed under Payment / Transfer move to Car Payment.
- Every row in Refund moves to the category of its purchase. A row there that is not a
  refund becomes what it is, such as a transfer back from the account that holds loans.
- Rows filed under Services that belong elsewhere, such as a utility bill or a rental, move
  to their category.
- Refund and Reimbursable are archived once empty.

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

The technical approaches are settled next.
