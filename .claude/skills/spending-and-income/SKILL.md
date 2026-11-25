---
name: spending-and-income
description: Use when Angelo asks how much he spent or earned, on what, or how a period compares with another, such as "cuánto gasté", "cuánto gané", "en qué se me fue la plata", "compara este mes con el anterior", "cuánto me costó el viaje" or "cuánto me subió el sueldo". Picks the periods, runs quaestor report through the installed CLI, and explains the figures it prints, always naming the rate.
---

# spending-and-income

Answer Angelo's questions on what he spent and earned with the figures `quaestor report` prints. `quaestor` computes every figure; you choose the periods and filters to ask for and explain what the figures mean. Talk to Angelo in Spanish.

## How to call quaestor

- Always the installed `quaestor`, the release, which defaults to `prod`. Never through `pnpm`, and never with `--env`. A store command prints `env: prod` on stderr first; if that line says anything else, stop and tell Angelo.
- Output is TOON; read it as printed. An amount comes back as a number: `45000.5` is 45.000,50.
- Refer to groups and categories by code. Show Angelo names, never codes.
- `quaestor` is the only way in. Never open the database, write SQL or touch the data folder.

## Rules

- Every figure you give comes from a `report` line, group or category exactly as printed. Never add or convert figures yourself; ask `quaestor` for the period or filter that gives the figure directly. To compare two periods, give both figures as printed.
- `total` is in COP. Each foreign currency counted adds a column with the part that was in that currency, in that currency. Say the rate in every answer: "a 4.000 COP por USD".
- One question per message. Wait for the answer before the next.
- No write without a dry run Angelo has seen and approved. The write after his yes is exactly the dry run's command without `--dry-run`.

## Reading a report

```sh
quaestor report --from 2026-10-01 --to 2026-10-31
```

- `totals` always has four lines: `income`, `spending`, `left` (income less spending) and `outside`.
- Spending is positive. A refund lowers its category, so a category can be negative in the month the money came back: shoes bought on 28 October and refunded on 3 November leave Clothing up in October and down in November. Say so when a month looks odd.
- An income below zero means money went out of an income category, such as a salary reversal. Say what it is.
- `outside` is never spending or income: payments and transfers, and changes in an investment's value, with their sign. An investment that fell shows as a negative `outside`. Mention it apart from what he spent.
- `groups` and `categories` list only what had movements. Each group opens into its categories through the category's `group` code.

## Choosing the period

- "Este mes", "el mes pasado": the calendar month, 1 to its last day.
- A month in progress is compared with the same days of the month before, in two calls: on 25 November, `--from 2026-11-01 --to 2026-11-25` against `--from 2026-10-01 --to 2026-10-25`.
- "Este año": 1 January to today.
- A trend, such as one category or the salary month by month: one call over the whole range with `--by-month`. Every month in it has its four `totals` lines, so a month without salary shows as 0.
- A trip: `--tag trip:lima-2026` for what it cost; `--without-tag trip:lima-2026` for the rest of the period. A trip counts as any other spending in the plain report.
- One merchant: `--payee uber`, which ignores case and accents.
- Answers cover only what is recorded. The salary history starts with the first recorded movement; say so when he asks about earlier years.

```sh
quaestor report --from 2026-01-01 --to 2026-11-25 --by-month
quaestor report --from 2026-09-01 --to 2026-09-30 --tag trip:lima-2026
quaestor report --from 2026-01-01 --to 2026-11-25 --payee uber
```

## When a command fails

- `missing_rate` names the `currencies` with no rate. Ask Angelo the rate of each, one per message, as COP per unit with at most two decimals. Show the dry run, and set it after his yes:

  ```sh
  quaestor rate set USD 3912.45 --dry-run
  quaestor rate set USD 3912.45
  ```

  `before` and `after` show the old and the new rate; `before: null` means there was none. Then run the report again.
- `not_found` with `kind: tag`: the tag is misspelt. Read `quaestor tag list` and ask which one he meant; never answer 0 for it.
- `invalid_input` lists every problem as `<field>: <what is wrong>`. Fix the call and run again.
- Exit 2: stop and tell Angelo what stderr said. Do not retry or work around it.

## Groups and categories

Every category belongs to one group, and each group is of one kind: spending, income or outside the totals. Changing them changes past answers too, so each change is a write: show the dry run, and run it after Angelo's yes.

```sh
quaestor group list
quaestor category list
quaestor group add Kids --emoji 👶 --kind spending --dry-run
quaestor group edit k4tr --name Children --emoji 🧸 --dry-run
quaestor group delete k4tr --dry-run
quaestor category add Toys --emoji 🧸 --group k4tr --dry-run
quaestor category edit n8d3 --group q3rh --dry-run
quaestor category archive n8d3 --dry-run
```

- A group's kind is fixed once created.
- A group that still holds a category, archived ones included, is refused as `group_not_empty` with its `categories`: move each with `category edit` first.
- An archived category keeps counting in its group and takes no new movement.
