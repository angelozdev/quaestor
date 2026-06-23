# 0016. Chat tool-error recovery: degrade LLM tool-call mistakes to isError, never 500

- **Status:** accepted
- **Date:** 2026-06-22
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —
- **Related:** ADR-0014 (chat endpoint + LiteLLM + MCP bridge), ADR-0015 (frontend request wire format)

## Context and problem statement

`POST /api/chat` (ADR-0014) currently crashes the SSE stream with HTTP 500
whenever an MCP tool call raises an exception. The first observed case: the
LLM (MiniMax-M3 via LiteLLM) called `monthly_report` with `"inp": ""`
(instead of the required `{month: "YYYY-MM"}` object). The fastmcp runtime
raised `fastmcp.exceptions.ToolError: Input should be a valid dictionary or
instance of MonthlyReportInput [type=model_type, input_value='', input_type=str]`,
which propagated out of `chat/service.py::ChatService.stream` because the
existing `try/except` only handles `ToolNotFoundError` and
`asyncio.TimeoutError` per tool — not the broader `ToolError`. Starlette then
turned the unhandled exception into a 500 to the client. The frontend
`useChat` saw the network error and surfaced the generic
"No pudimos contactar al servidor" banner; the user lost their conversation.

This is a **general** class of failure, not a `monthly_report` bug. Any LLM
in production can call any tool with malformed arguments, mistype a field
name, or invent a value the schema rejects. If the backend 500s on every
such mistake the chat is unusable for the long tail of model behavior —
which is the entire reason we have an LLM in the loop.

## Decision drivers

- **Availability over strictness.** A chat turn that the LLM botched is not a
  server error; it's a recoverable runtime condition. The user must keep
  their conversation and see a friendly message, not a 500.
- **Honor the SSE contract.** The Vercel AI SDK UI Message Stream protocol
  already defines a top-level `error` event with `errorText`; the frontend's
  `chat-errors.ts` already maps messages starting with `errorText:` to a
  user-facing string. We use it — no new wire format.
- **Let the LLM self-correct when it can.** When a tool raises, the LLM
  often can recover on the next iteration (different args, different tool,
  or just answer the user without the tool). Feeding the error back as a
  `tool-output-available` with `isError: True` is the natural way to do
  this; the model loop is already designed for it.
- **Don't mask programmer errors.** The `assert`s in `MCPClient` (e.g.
  "use `async with MCPClient(...)`") and any other unexpected exception
  type must still propagate so a real bug gets a 500 + a log line, not a
  silent swallowed event.
- **Match the existing pattern.** ADR-0014 already catches
  `UpstreamLLMError`, `asyncio.TimeoutError`, and `ToolNotFoundError` at
  well-defined boundaries and converts them to SSE events. This decision
  extends that same pattern, not a new one.

## Considered options

1. **Degrade tool errors to `tool-output-available` `isError: True` and
   continue the loop; let top-level exceptions still 500** (chosen).
2. Catch **every** exception at the top of `stream()` and emit a single
   top-level `error` event, ending the stream.
3. Validate LLM tool arguments *before* dispatch (defensive pre-checks
   against the registered tool schema).
4. Change the LLM prompt to instruct it to never call a tool with empty
   arguments.

## Decision outcome

Chosen option: **1**, because it matches the existing per-tool error path
(the `ToolNotFoundError` and `asyncio.TimeoutError` branches already do
exactly this), reuses the LLM's own recovery loop, and preserves the 500
signal for the small set of exceptions we genuinely don't expect.

### Pros and cons of the options

**Option 1 — per-tool `except Exception` → `isError` + continue**
- Good: minimal blast radius; only changes the per-tool dispatch block in
  `chat/service.py`. No new abstraction, no new wire event.
- Good: lets the LLM self-correct on the next iteration. Empirically
  models do this well — they see the error message and either retry with
  better args or answer the user from what they already know.
- Good: reuses the existing `tool-output-available isError` SSE event
  (ADR-0014 §"SSE protocol") — frontend's `chat-errors.ts` already
  understands it.
- Bad: surfaces raw exception messages in the conversation. We truncate
  to one line and prefix with a friendly tag so the LLM (and the user, in
  the rare leak case) sees a useful hint instead of a Pydantic stack dump.

**Option 2 — top-level `except Exception` → top-level `error` + end**
- Good: trivially simple; one new `try/except` wraps the whole stream.
- Bad: ends the conversation on the first tool failure, even when the
  LLM could have recovered. Wastes the rest of `CHAT_MAX_ITERATIONS`
  budget and the user's turn.
- Bad: silent on real bugs. A `KeyError` in our own code would emit
  `errorText: "KeyError: 'foo'"` and end the stream instead of crashing
  loudly in logs.

**Option 3 — pre-validate LLM tool arguments against the tool schema**
- Good: rejects bad calls before they hit MCP, so the LLM never sees a
  Pydantic trace.
- Bad: requires re-implementing FastMCP's schema validation. Duplicates
  logic that already lives in fastmcp and drifts when MCP evolves.
- Bad: changes the trust boundary — we'd be validating LLM output
  ourselves instead of letting the tool runtime do it. Higher surface
  for new bugs.

**Option 4 — prompt engineering ("never call a tool with empty args")**
- Good: zero code change.
- Bad: doesn't generalize. A model that mistypes `month` as `monht`
  still calls `monthly_report({monht: "2026-06"})` and we 500.
- Bad: prompts drift. The LLM provider or the model itself can change
  the behavior at any time, and we'd 500 again with no warning.

## Consequences

- **New code path in `chat/service.py`**: a single `except Exception` after
  the existing `except asyncio.TimeoutError` in the per-tool dispatch
  block. Emits `tool-output-available` with `isError: True` and a
  one-line truncated error message, appends a `role: "tool"` message
  carrying the same text to the in-request conversation, and continues
  the loop. The MCP client context is **not** closed — the next tool
  call (or the next provider turn) reuses the same session, which is
  what we want.
- **No SSE protocol change.** The `error` top-level event is still
  reserved for unrecoverable transport-level failures (upstream LLM
  error, request timeout). The new path produces a *tool-level* error
  event, which the protocol already supports and the frontend already
  understands.
- **Frontend unchanged.** `chat-errors.ts` already handles
  `tool-output-available` with `isError: true` — the `<ChatToolChip>`
  auto-expands the pill and shows the error text. The user sees a
  colored chip in the transcript and the LLM gets a chance to recover.
- **Observability.** A `console.error` log line carries the raw
  exception (type + message + truncated traceback) for every caught
  tool error. No new metrics, no new dashboard; the runbook in
  `docs/runbooks/chat-endpoint.md` (added with ADR-0014) gets a
  one-line addendum: "tool errors in the loop are expected and
  recoverable; only top-level `error` events are user-visible alerts."
- **Failure mode is still loud for real bugs.** `MCPClient.__aexit__`
  failures, `MCPClient.call_tool` bugs, the `assert`s in
  `MCPClient`, and any other exception that escapes the per-tool
  `try/except` still 500. This is what we want.

## Confirmation

- A new test in `tests/chat/test_service.py` mocks
  `MCPClient.call_tool` to raise `fastmcp.exceptions.ToolError`
  (the exact class the production case used), drives a two-step
  scripted LLM (call tool → answer with text), and asserts that
  the SSE stream contains a `tool-output-available` event with
  `isError: True` **and** a `text-delta` event from the second
  iteration — proving the loop survived and the LLM got a chance
  to recover.
- The existing test
  `test_tool_error_emits_is_error_and_loop_continues` is the
  positive counterpart (tool returns `is_error: True` instead of
  raising) and stays green.
- `uv run pytest` — 552 + 1 = 553 pass.
- Manual: the user's failing curl now returns 200 with a friendly
  `errorText:` event for the bad `monthly_report("")` call, and
  the LLM recovers with a textual answer in the same turn.
- The chat runbook gets the one-line addendum noted above.
