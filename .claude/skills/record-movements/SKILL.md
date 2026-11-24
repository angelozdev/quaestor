---
name: record-movements
description: Use when Angelo sends bank screenshots or a statement, or asks to "anotar", "registrar movimientos" or "poner al día la cuenta". Transcribes the rows, shows a dry run with each account's balance before and after, and writes through the installed quaestor CLI only after his yes.
---

# record-movements

Keep Quaestor equal to the bank. Angelo sends screenshots of his bank apps, you read them, `quaestor` stores them. Talk to Angelo in Spanish. Everything you send to `quaestor` follows the formats below.

## How to call quaestor

- Always the installed `quaestor`, the release, which defaults to `prod`. Never through `pnpm`, whose script writes to the test store, and never with `--env`. A store command prints `env: prod` on stderr first; if that line says anything else, stop and tell Angelo.
- Output is TOON; read it as printed. An amount comes back as a number: `45000.5` is 45.000,50.
- Refer to accounts and categories by code (two categories can share a name) and to tags by name. Show Angelo names, never codes.
- `quaestor` is the only way in. Never open the database, write SQL or touch the data folder.

## Rules

- One question per message. Wait for the answer before the next.
- Only a bank statement creates a movement. An app's activity list (rides, deliveries, shops) only helps label a bank row: its payee, category, tags or note. A row that only an app shows is never recorded.
- A row the bank marks as pending is asked about, not decided: ask Angelo whether to record it now or wait until it posts.
- No write without a dry run Angelo has seen and approved. The write after his yes is exactly the dry run's JSON; if anything changes, dry run again.
- A difference with the bank's balance is investigated and never adjusted. No balancing row, no made-up category, no amount bent to fit.
- A correction is a delete and a record in one write. A movement is never edited in place.

## The session

1. Read what is there. Match the screenshot to an account by name and currency, and ask if unsure.

   ```sh
   quaestor account list
   quaestor movement list --account n8d3 --from 2026-11-01
   ```

   `account list` gives each account's code, currency, archived mark and balance today. Start `--from` a few days before the screenshot's oldest row. `total` counts every match; if it is more than the rows listed, add `--limit <n>`. Each row's `balance` is the account's balance after that movement.

2. Transcribe every row: the date the bank shows, the payee as printed, the signed amount in the account's currency. Note the bank's balance and the day it is for.

3. Drop the overlap and what is already recorded. A row is recorded when account, date and amount match a listed movement; match one for one, so two identical rows on screen and one recorded leave one to record. Tell Angelo in one line what you dropped.

4. Propose each row's category and tags from how its payee was categorised before.

   ```sh
   quaestor movement list --payee sunrise
   quaestor category list
   quaestor tag list
   ```

   `--payee` ignores case and accents. Reuse the category and tags of the payee's latest movements. A category or tag that is not listed is refused, and so is an archived category.

5. Ask only what you cannot infer, one question per message, with your best guess in it.

6. Dry run: the JSON goes on stdin, every amount is text.

   ```sh
   quaestor movement write --dry-run <<'JSON'
   {
     "delete": ["h4vw"],
     "movements": [
       {
         "account": "n8d3",
         "date": "2026-11-20",
         "payee": "Sunrise Bakery",
         "amount": "-15000",
         "currency": "COP",
         "category": "r3sb",
         "tags": ["who:alex"],
         "note": "breakfast"
       }
     ],
     "transfers": []
   }
   JSON
   ```

   `delete`, `movements`, `transfers`, `tags` and `note` may be left out, but a write names at least one change. The output lists `deleted`, `recorded` and `balances[]` with `account`, `currency`, `before` and `after`.

7. Compare before asking for the yes. For every touched account, set `balances[].after` beside the bank's balance, to the cent.
   - Equal: show Angelo each movement (date, payee, amount, category, tags), each deletion, and each account's balance before and after next to the bank's, and ask for the yes.
   - Different: look for the cause in this write first: a row missed or dropped wrongly, a wrong sign, a thousands dot read as a decimal, a pending row, a fee or interest the screenshot does not show. Fix it and dry run again. A cause that is a real movement is recorded with its category (bank interest, a refund, a fee) in the same write.
   - Still different: compare `before` with the bank's balance before these rows. If it is off by the same amount, the gap predates this write. Show Angelo the dry run with the difference stated in one line, and let him decide whether to write; investigate it with him after. Never add a balancing row.
   - `after` counts every movement the account has, whatever its date. If some are newer than the bank's balance, take them out of `after` first (`quaestor movement list --account n8d3 --from <next day>`).

8. After the yes, run the same `quaestor movement write` without `--dry-run`, with the same JSON.

9. Compare the final balance with the bank's.

   ```sh
   quaestor account list
   quaestor movement list --account n8d3 --to 2026-11-20 --limit 1
   ```

   The first gives the balance today; the second gives the `balance` after the last movement on or before the bank's day. A difference is investigated with Angelo; once its cause is found it is recorded as a real movement with its category, never adjusted.

## Amounts

- Write the amount as the bank shows it, with a dot before at most two decimals and no thousands separator. Positive is money in, negative is money out, and zero is refused.

  | The bank shows | Write |
  | --- | --- |
  | COP $45.000,50 | `"45000.50"` |
  | COP -$15.000 | `"-15000"` |
  | USD $10,85 | `"10.85"` |
  | KRW ₩15.000 | `"15000"` |

- On a COP or KRW screen the dot separates thousands. `"-15.000"` is refused for its three decimals, but `"-15.00"` passes silently as 15 pesos; only the balance comparison catches it.
- A movement is always in its account's currency, and `currency` must match it. A purchase in another currency is what the account was charged: 500 MXN paid from a USD account that was charged 28.00 is `"-28.00"` in `USD`. Put the original amount in `note` when Angelo wants it.
- Nothing converts between currencies and nothing adds two currencies together.

## Transfers

Paying a card, moving money to savings and lending are transfers: two halves, each in its own account, currency, date and payee, with no category. `from` is negative and `to` is positive.

```json
{
  "transfers": [
    {
      "from": { "account": "w2k9", "date": "2026-11-21", "payee": "To Bank", "amount": "-100", "currency": "USD" },
      "to": { "account": "n8d3", "date": "2026-11-21", "payee": "From Wallet", "amount": "400000", "currency": "COP" }
    }
  ]
}
```

- Both halves go in one write. If only one half is on a statement in hand, ask Angelo for the other account's statement, or whether the other half has posted.
- Across currencies, `quaestor` compares nothing. Check the rate the two amounts imply (400000 / 100 = 4.000 COP per USD) against the statements.
- Deleting one half deletes both. To correct a transfer, delete it and record both halves again, in one write.

## Something does not exist yet

An unknown category or tag is never invented to make a write pass. Creating one is its own write, with its own dry run and Angelo's yes, before the movement write.

```sh
quaestor tag add trip:lima-2026 --dry-run
quaestor category add Bakery --emoji 🥐 --dry-run
quaestor account add Savings --emoji 🏦 --type savings --currency COP --opening 500000 --opening-date 2026-11-01 --dry-run
```

After the yes, run the same command without `--dry-run`. A category is an emoji and an English name. A tag is lowercase letters, digits, colons and dashes. An account's opening balance is what the bank showed the day before the first row you will record; ask Angelo for it.

## When a command fails

- Exit 1, with stdout empty: nothing was written. stderr has `error:` with a `code` (`refused`, `invalid_input` or `invalid_json`) and every item at fault, such as `movements[2]` or `transfers[0].from`. Fix every listed item, dry run again, and show Angelo the new dry run.
- Exit 2: stop and tell Angelo what stderr said. Do not retry or work around it.

## Not part of a session

`quaestor import` loads the legacy export once, into an empty store; never run it here. `quaestor backup` copies the store to its backups folder; run it only when Angelo asks.
