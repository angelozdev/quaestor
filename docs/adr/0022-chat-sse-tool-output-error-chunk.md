# 0022. Chat SSE tool-output-error chunk

- **Status:** proposed
- **Date:** 2026-06-28
- **Deciders:** Angelo
- **Supersedes:** —
- **Superseded by:** —

## Context and problem statement

The chat endpoint (ADR-0014) emits the Vercel AI SDK UI Message Stream
protocol. ADR-0018 adopted three best practices from Vercel's reference
template but did not catch a fourth divergence: when an MCP tool call
fails (raises an exception, times out, returns `is_error=True`, or names
an unknown tool), the SSE chunk is rendered as

```json
{"type": "tool-output-available", "toolCallId": "tc_1", "output": "...", "isError": true}
```

with `isError: true` attached as an extra field. The AI SDK v3 React
client validates every chunk through `uiMessageChunkSchema` (defined in
`frontend/node_modules/ai/dist/index.mjs:5396+`), whose
`tool-output-available` variant is a `z7.strictObject` that does not list
`isError` as a known field. Strict-mode rejects unknown keys, so the
chunk fails the union validation. The frontend's
`DefaultChatTransport.processResponseStream` throws and the user sees a
"Type validation failed" error.

The official AI SDK protocol defines three distinct tool-output chunks
(verified in `frontend/node_modules/ai/dist/index.mjs:5463-5485`):

| Chunk | Field set |
|---|---|
| `tool-output-available` | `type`, `toolCallId`, `output` (strict — no `isError`) |
| `tool-output-error` | `type`, `toolCallId`, `errorText` |
| `tool-output-denied` | `type`, `toolCallId` (minimal) |

ADR-0018's review missed this because the in-tree tests
(`backend/tests/chat/test_service.py`) parse SSE with a custom
`_parse_sse` helper that does only `json.loads`, never round-tripping
through the SDK's zod schema. The drift is invisible in CI.

## Decision drivers

- Wire compatibility with the AI SDK v3 React client (the chosen
  frontend transport per ADR-0014).
- No 500s on tool errors (ADR-0016): the LLM must still see the error
  on its next iteration and self-correct.
- The in-conversation tool message (OpenAI shape, sent to the LLM
  provider) is independent of the SSE wire shape and stays unchanged.
- No new dependencies — the strict-shape regression test is a hand-written
  Pydantic `extra="forbid"` model that mirrors the SDK's schema.

## Considered options

1. **Emit a separate `tool-output-error` chunk for failures; reserve
   `tool-output-available` for success only.** Keep the success variant's
   strict schema, render errors with the documented `errorText` field.
2. **Drop the `isError` field from `tool-output-available` and rely on
   the LLM to read the `output` text for failure cues.** Loses the
   discriminated union's affordance — the frontend can't distinguish
   success from failure at the chunk level — and breaks tools that
   return legitimate string outputs that happen to look like errors.
3. **Pin the AI SDK to v2 where the schema is lenient.** Regressive:
   the project is on v3 (per `frontend/package.json`); downgrading
   forfeits all v3 features (reasoning parts, attachments, etc.).

## Decision outcome

Chosen option: **1**. The SSE serializer renders tool errors as
`{"type": "tool-output-error", "toolCallId": ..., "errorText": ...}`.
The success variant (`tool-output-available`) carries no `isError` field
and emits only when the tool ran successfully. The four tool-error
paths in `chat/service.py` (tool-not-found, timeout, generic exception,
and the success-with-`is_error=True` from a tool that returned an error
result without raising) all switch to the new variant.

The `LLMEvent` and `LLMEventType` enums gain one variant each
(`TOOL_OUTPUT_ERROR`, `error_text`); the success-side fields
(`output`, `is_error`) stay for the success-only emit path so that the
service can pass `result.is_error` through to the renderer for the case
where a tool's `call_tool` returned an error result rather than raising.
The LLM-facing conversation history (assistant tool_calls + tool
messages) is unchanged.

The behavior test in `tests/chat/test_sse_schema.py` round-trips every
chunk the service emits through a Pydantic Strict model that mirrors
`uiMessageChunkSchema` for the variants we emit. The existing
`_parse_sse` helper in `tests/chat/test_service.py` is kept for
shape-inspection tests but is not the wire validator.

## Consequences

- Good: the AI SDK v3 React client stops throwing on tool errors; the
  chat UI shows the error text in the tool invocation and continues
  the loop.
- Good: future drift in other chunk types is caught by the same
  behavior test (every emitted chunk validated, not just the new one).
- Good: no new dependencies — Pydantic `extra="forbid"` is the
  Python equivalent of zod `strictObject`.
- Bad / cost: callers that hand-rolled SSE parsing on the wire and
  read the `isError` field see a behavior change. There are no in-tree
  callers (the only consumer is the AI SDK React client); external
  scripts should be flagged in release notes.
- Follow-up: when the LiteLLM provider gains `provider-executed` tool
  calls, the `providerExecuted` field on `tool-output-error` becomes
  relevant. Out of scope today.

## Confirmation

- `tests/chat/test_sse_schema.py::test_every_emitted_chunk_passes_strict_schema`
  drives a tool-call-then-error scenario, parses the SSE bytes, and
  validates every chunk through the Pydantic Strict model. Fails on
  the current code (the `isError` extra field), passes after the fix.
- `tests/chat/test_sse_schema.py::test_tool_error_chunk_has_required_fields`
  asserts the exact shape `{type: "tool-output-error", toolCallId, errorText}`
  for a tool-not-found, tool-timeout, and tool-raise scenario.
- `tests/chat/test_sse_schema.py::test_tool_success_chunk_has_no_is_error_field`
  asserts that the success variant never carries `isError` (locks the
  regression against re-introducing the field).

## Related

- ADR-0014 — chat endpoint base.
- ADR-0016 — tool-error recovery (the behavior is unchanged; only the
  wire shape changes).
- ADR-0018 — Vercel template best practices (the divergence this ADR
  corrects was not caught during the ADR-0018 review because the
  in-tree tests bypassed the SDK's zod schema).
- `frontend/node_modules/ai/dist/index.mjs:5463-5485` — the wire
  schema this ADR adopts.
