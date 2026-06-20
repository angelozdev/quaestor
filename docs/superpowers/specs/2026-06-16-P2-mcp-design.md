# Quaestor — P2 MCP server (sub-project)

**Date:** 2026-06-16
**Depends on:** P0 (core: domain + base services)
**Part of:** `2026-06-16-quaestor-general-design.md` (see architecture §3, deployment/auth §4, services §7)

---

## Objective

Expose Quaestor as a **natural-language interface** for any MCP client (Claude Code today; MiniMax or another tomorrow). The user talks to an agent —"I spent 40k on groceries", "what do I have to pay this week?"— and the agent records, queries, and operates the backend through **MCP tools**. The server is a **thin adapter** over `services`: it translates the agent's intent into use-case calls and returns text/markdown that the agent explains back to the user. It is **LLM-agnostic**: no client is hard-wired, only the MCP protocol.

## Scope

- **MCP server with the official Python SDK**, exposed over the **streamable-HTTP** remote transport at the `/mcp` path. **Defense in depth (ADR-013):** the endpoint is **not on the public internet** — a **Tailscale** sidecar serves it inside the private network (P7); on top of that, every request requires the **bearer token (`APP_TOKEN`)** in the header. The token is no longer the only thing protecting the sensitive endpoint.
- **Why remote and not local stdio:** the user doesn't want to run the backend on their laptop. Quaestor lives on the VPS. With stdio you'd have to keep a local process (or a shim) pointing at `quaestor.db`. With streamable-HTTP, Claude Code connects to the server's URL —served by Tailscale on the tailnet, not by Caddy— and the server runs alongside `services`/DB on the VPS. (Requirement: the user's machine is on the same tailnet; see the trade-off in §4/ADR-013.)
- **Core tools (P2 kickoff):** `record_expense`, `record_income`, `transfer`, `set_fx_rate`, and the reads (`get_*` / `list_*`: transactions, accounts, categories, tags, current rate).
- **Does not include** the feature tools: `create_recurring`/`list_recurring`, `plan_payment`/`confirm_payment`/`to_pay` (P3 — `close_month` is **not** a tool, the scheduler runs it, ADR-017); `set_budget`/`budget_status`/`safe_to_spend`/`create_goal`/`goal_contribution`/`goals_progress` (P4); `monthly_report`/`import_csv` (P5). P2 leaves the **registration pattern ready** so each one plugs in its tools without touching the transport or the auth.
- **Out of scope:** domain logic (lives in `services`/`domain`, P0), the REST API (P1), the frontend (P6).

## Contribution to the data model

**None.** P2 creates no entities, columns, or migrations. It is a pure inbound adapter: each tool ends up in a service that already operates on the model defined in §5 of the general design. Just like the API (P1), the MCP server **is the same brain seen through another door**; adding tables here would break the golden rule (§3: adapters never touch the DB or redefine the model).

## Components

Under `backend/src/quaestor/mcp/`:

- `server.py` — builds the official SDK's MCP instance, mounts the streamable-HTTP transport at `/mcp`, applies the auth middleware, registers the tools. Entry point `python -m quaestor.mcp`.
- `auth.py` — verifies the `APP_TOKEN` bearer from the header on every request to the transport; rejects if it's missing or doesn't match.
- `registry.py` — the **registration pattern**: a `register_core_tools(mcp, ...)` function that P2 implements, plus the convention for P3/P4/P5 to expose their own `register_*_tools(mcp, ...)` and for `server.py` to invoke all of them. Growing = adding a line, not touching the transport.
- `tools/core.py` — the core tools (expenses, income, transfers, FX, reads). Each one: parses input (Pydantic schema), calls the service, formats the output as text/markdown.
- `format.py` — helpers to render service results (recorded transaction, list, balance, rate) into readable markdown, and to turn domain errors into clear text.

One DB session per request (same discipline as the API), passed to the service. Tools don't open their own engines or sessions outside that scope.

## Public interface (MCP tools)

1 tool = 1 service, same verbs. The **schemas are derived from Pydantic** (one input model per tool → JSON Schema that the SDK publishes to the client). The output is **structured text/markdown**, not raw objects.

Core tools in P2:

| Tool | Service | Input (key fields) | Output (text/markdown) |
|---|---|---|---|
| `record_expense` | `transactions.record_expense` | `payee`, `amount`, `currency`, `account`, `category?`, `date?`, `tags?`, `notes?` | confirmation: amount, account, `to_base` COP, new balance |
| `record_income` | `transactions.record_income` | same as expense | equivalent confirmation |
| `transfer` | `transactions.transfer` | `from_account`, `to_account`, `amount`, `currency`, `date?`, `notes?` | pair created (source/destination), resulting balances |
| `set_fx_rate` | `fx.set_rate` | `date`, `usd_cop` | rate recorded for the date |
| `list_transactions` | reads | filters: `from?`, `to?`, `account?`, `category?`, `tag?`, `type?`, `status?` | markdown table + totals |
| `list_accounts` | reads | — | accounts with balance and currency |
| `list_categories` | reads | — | categories + group + flags |
| `get_fx_rate` | `fx.current_rate` | `date?` | current rate for the date |

Conventions the tools inherit: amounts as **integers in cents** in the original currency; **sign by `type`** (not in the amount); aggregates/balances in `to_base` COP; on recording, `status=posted` by default and `source=agent`. They accept readable names (account/category/tag by name, not by id) and the adapter resolves them before calling the service.

## Logic and key rules

- **Zero domain logic in P2.** Validating, converting FX, balancing transfers, updating balance → all in `services`/`domain`. The tool only adapts the input/output shape.
- **Each tool calls one service; never touches the DB.** Identical brain to the API.
- **Name resolution:** the agent speaks in names ("Bancolombia", "Groceries"); the tool resolves them to entities via a read service. If it doesn't exist, it returns text suggesting the right option or to create the entity.
- **Friendly defaults:** missing `date` → today; missing `currency` → base currency (COP). This reduces friction in natural language, but the amount is always passed explicitly.
- **Output designed for the agent:** short, structured markdown that the LLM can paraphrase (not raw JSON). It includes the data point that closes the loop: new balance after an expense, `to_base` on a USD tx, total on a query.
- **Growth pattern:** when P3/P4/P5 land, they register their tools via `register_*_tools` without touching `server.py` except for one line of wiring. The transport and the auth are not re-litigated.

## Errors

- **Domain errors are returned as clear text, not raw exceptions.** The adapter catches the typed errors from `domain` (`ValidationError`, `MissingRate`, `TransferImbalance`…) and formats them so the agent can explain them. E.g.: `MissingRate` → "I don't have the USD→COP rate for that date. Give me the rate with `set_fx_rate` and I'll retry." A stack trace never reaches the client.
- **Auth:** a request without a valid bearer → the transport responds with a protocol-level rejection (no tool runs).
- **Atomicity:** transfers commit/rollback in the service (both transactions or neither); if it fails, the tool reports text and the DB stays intact.
- **Invalid input** (missing field/wrong type) → the Pydantic schema validates it before touching the service; the SDK returns the detail to the client.

## Testing and the "done" criterion

- **Unit/adapter:** each tool with the real service over **in-memory SQLite** — record expense/income, transfer, set/get FX, list/query. Verifies output formatting and the translation of domain errors into text (no raw exceptions).
- **Auth:** a request without a token or with the wrong token → rejected; with the correct `APP_TOKEN` → passes.
- **Registration pattern:** all the expected tools end up exposed after `register_core_tools`; an additional `register_*` mounts without touching the transport.
- **"Done" criterion:** from **Claude Code connected to the remote `/mcp`**, the user **records a transaction speaking in natural language** (e.g. "I spent 50k on lunch with the debit card") and then **queries the result** ("how much have I spent today?") getting back the just-created transaction. The full loop NL → tool → service → text works against the real backend.

## Integration with other sub-projects

- **How Claude Code connects:** the user's machine is on the tailnet; MCP config points at the VPS's **MagicDNS** (`https://quaestor-mcp.<tailnet>.ts.net/mcp`), with the `APP_TOKEN` in the header. The Tailscale sidecar serves `/mcp` → MCP server (§4/ADR-013); **it doesn't go through Caddy or the public internet**. **MiniMax:** plugs in the same way once it supports remote MCP and is on the tailnet; no changes to the server (it's LLM-agnostic).
- **P0 (core):** hard dependency. P2 consumes `services` and `domain` as-is; it doesn't modify them.
- **P1 (API):** symmetric sibling. Same services, different door (REST vs tools). Zero duplicated logic; they share `APP_TOKEN`.
- **P3/P4/P5:** register their feature tools through the `registry.py` pattern. Each one contributes its services and its `register_*_tools`; P2 has already left the transport, the auth, and the formatting ready. P4 exposes, among others, the **safe-to-spend** ("how much do I have free this month?") — the agent-native question that LM doesn't answer.
- **P7 (deployment):** runs the MCP server as the `mcp` service in `docker-compose.yml`, **served by the Tailscale sidecar** (not by Caddy, ADR-013), with `APP_TOKEN` via env and the same `quaestor.db` (volume) as the API and rollover.
