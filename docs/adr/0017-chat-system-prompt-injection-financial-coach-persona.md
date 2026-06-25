# 0017. Chat system prompt: server-side injection of a financial coach persona

- **Status:** accepted
- **Date:** 2026-06-22
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —
- **Related:** ADR-0014 (chat endpoint + LiteLLM + MCP bridge), ADR-0016 (tool error recovery)

## Context and problem statement

`POST /api/chat` (ADR-0014) ships a stateless agentic loop that forwards the
frontend-supplied message history verbatim to LiteLLM and exposes every MCP
tool (ADR-0009 parity) for the LLM to call. Up to now the LLM ran with **no
system message at all** — neither server nor client injects one. The result
is generic, provider-default behavior: terse answers in English, no persona,
no methodology, no domain framing. Users get a chatbot bolted onto a finance
app, not a coach.

The product is a personal-finance tracker (P0). The natural-language surface
exists to answer questions like "¿cuánto llevo de comida esta semana?" and
to nudge the user toward healthier money habits. That requires the model to
adopt a specific persona — a calm, non-judgmental financial coach grounded
in the user's real data — and to follow a methodology: clarify before
recording, summarize with numbers, never invent a transaction.

The frontend already sends the full message history per turn (ADR-0015);
injecting the system prompt client-side would duplicate the persona text on
every request and force a re-deploy of the Next.js app to change it.
Injecting on the server keeps it in one place, next to the MCP tool
registry it describes.

## Decision drivers

- **Single source of truth for the persona.** Today the only knob we have is
  the prompt itself; changing tone, language, or methodology must be a
  single edit.
- **Deploy-specific.** Production, staging, and local dev may want
  different personas (e.g. dev wants verbose tool traces; prod wants a
  quiet coach). Env var fits this without code branches.
- **Token-budget aware.** The chat endpoint already caps the request at
  100 k estimated tokens (ADR-0014). The system prompt must be small
  enough that legitimate conversations still fit.
- **Tool-first, never invent.** The MCP tool set (52 tools, ADR-0009) is
  authoritative. The persona must instruct the model to call tools for
  every concrete number and never fabricate a transaction, balance, or
  category that the user did not explicitly provide in this turn.
- **Bounded advice.** A "financial coach" must not stray into regulated
  advice (investments, tax strategy, legal). The persona sets the line.
- **Backwards compatibility.** If the env var is unset, behavior must be
  identical to today (no system message). No regression in tests that
  don't know about this ADR.

## Considered options

1. **Server-side prepend in `ChatService` from `CHAT_SYSTEM_PROMPT` env var**
   (chosen).
2. Frontend prepend — `useChat` injects the system message on every send.
3. Static constant in `chat/service.py` with no env override.
4. LiteLLM `system` parameter (separate from `messages`) — LiteLLM hoists
   it to a top-level field on Anthropic/OpenAI.

## Decision outcome

Chosen option: **1**, because it centralizes the persona in the deploy
artifact (env), keeps the frontend stateless per ADR-0015, and matches the
existing pattern in `factory.py` (env-driven config: `LLM_PROVIDER`,
`LLM_MODEL`, `CHAT_MAX_ITERATIONS`, `CHAT_REQUEST_TIMEOUT_S`).

### Pros and cons of the options

**Option 1 — server-side prepend, env-driven**
- Good: one source of truth; ops can tune without a code change.
- Good: zero frontend changes; ADR-0015's wire format stays valid.
- Good: trivially disabled in tests (just unset the env var).
- Good: matches `factory.py`'s "env is the configuration surface" pattern.
- Bad: adds one env var to the deploy contract. Acceptable — see
  "Configuration" below.
- Bad: if the env var is set with multi-MB content, the request still
  fits under the 100 k token ceiling but eats the budget. We truncate.

**Option 2 — frontend prepend**
- Good: no backend change.
- Bad: persona lives in two places if we ever inject from the backend too
  (we will, for any non-web client).
- Bad: forces a frontend redeploy to tweak the prompt.
- Bad: `useChat`'s `DefaultChatTransport` already forwards messages
  verbatim; adding a pre-send hook is more code than the server change.

**Option 3 — static constant, no env**
- Good: simplest possible diff.
- Bad: dev/prod drift requires code branches or a redeploy for every
  wording tweak. Defeats the "single knob" goal.

**Option 4 — LiteLLM `system=` top-level param**
- Good: keeps the messages array free of admin messages.
- Bad: LiteLLM normalizes this differently across providers (Anthropic
  accepts a top-level `system`; OpenAI folds it into the messages array).
  Mixing shapes risks silent provider-specific behavior. We already
  have `messages` working end-to-end (ADR-0014); reuse it.

### The prompt itself

Lives in `backend/src/quaestor/chat/prompts.py::COACH_SYSTEM_PROMPT`. It is
a Spanish (Colombia, COP) persona with:

- **Role:** coach financiero personal, no asesor regulado.
- **Tool discipline:** concrete numbers (saldos, totales, presupuestos,
  progreso de metas) **siempre** vía tools MCP. Nunca inventar.
- **Methodology:** preguntar antes de registrar gastos/ingresos; resumir
  con cifras y contexto (mes, categoría, tendencia); preferir una
  recomendación concreta a una lista genérica.
- **Boundaries:** no asesoría de inversión, tributaria, ni legal;
  recomendar profesional cuando el usuario lo pida explícitamente.
- **Format:** respuestas cortas en español; cifras en COP con separador
  de miles; tablas solo cuando hay varias categorías para comparar.

### Configuration

- **Env var:** `CHAT_SYSTEM_PROMPT`. Empty / unset → no system message,
  pre-ADR-0017 behavior preserved.
- **Override path:** set it in the deploy env (Caddyfile systemd unit, or
  whatever wraps the backend container — same place that sets `APP_TOKEN`,
  `LLM_PROVIDER`, etc.).
- **Default in deploy:** the bundled `COACH_SYSTEM_PROMPT` constant is the
  default for the production env. Local dev and CI unset it.
- **Truncation:** if the env var exceeds **4 000 characters**, log a
  warning and truncate to 4 000 chars. 4 k chars ≈ 1 k tokens, well
  inside the 100 k request budget and small enough that the LLM actually
  reads it.

### Where the injection happens

`ChatService.stream(messages)` does `conversation = list(messages)` on
line 57. After this ADR, that line becomes:

```python
if self._system_prompt:
    conversation.insert(0, {"role": "system", "content": self._system_prompt})
conversation.extend(messages)
```

The prepended message rides the same `messages` array to the provider, so
the tool-call accumulator and the SSE shape are unchanged. User-supplied
`role: "system"` messages (already accepted by the Pydantic schema in
`api/chat.py`) are still preserved verbatim — they sit *after* our
injected one. If we ever need to override the server prompt with a
client-supplied one, the API can do that explicitly.

## Consequences

- **New module:** `backend/src/quaestor/chat/prompts.py` with the
  `COACH_SYSTEM_PROMPT` constant.
- **Modified:** `backend/src/quaestor/chat/service.py` accepts a new
  `system_prompt: str | None` constructor arg; prepends to `conversation`
  if set.
- **Modified:** `backend/src/quaestor/api/chat.py` reads
  `CHAT_SYSTEM_PROMPT` from env (with truncation + warning) and passes
  it to `ChatService`.
- **No frontend change.** `useChat` keeps sending only `user` and
  `assistant` messages. The persona arrives server-side.
- **No SSE wire change.** System messages never appear on the wire
  (they go upstream, not downstream). Existing `useChat` consumers are
  unaffected.
- **No token-budget change** beyond the 4 k-char prompt ceiling. The
  existing 100 k estimated-token limit in `api/chat.py::_validate_limits`
  still gates total request size.

## Confirmation

- New unit tests in `tests/chat/test_service.py`:
  - `test_system_prompt_prepended_when_set` — env-style `system_prompt`
    arg is injected as the first message sent to the provider; subsequent
    messages follow.
  - `test_no_system_prompt_means_no_injection` — `system_prompt=None`
    produces no system message (back-compat).
  - `test_user_supplied_system_message_kept_after_injected_one` — a user
    message with `role: "system"` is preserved *after* the injected one.
- New unit test in `tests/chat/test_api.py` or `test_api_limits.py`:
  - `test_chat_system_prompt_env_prepended_in_conversation` — drive the
    route end-to-end with the env var set; assert via the stub provider
    that the first `messages` arg it saw starts with
    `{"role": "system", "content": <prompt>}`.
  - `test_chat_system_prompt_env_truncates_at_4k` — set a 10 k-char
    prompt; assert the injected message content is ≤ 4 000 chars and a
    warning was logged.
- `uv run pytest` — all existing tests stay green; new tests pass.
- Manual smoke: a local `curl POST /api/chat` with a question like
  "¿cómo voy de presupuesto este mes?" produces a Spanish answer that
  references specific MCP tool calls (list_budgets, list_transactions)
  and renders amounts in COP with thousands separators.
