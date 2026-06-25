# 2026-06-23 — Adopt best practices from vercel-labs/ai-sdk-preview-python-streaming

## Context

The Quaestor chat endpoint (ADR-0014 → 0017) was built without an
authoritative Python reference for the Vercel UI Message Stream wire format.
We reverse-engineered the spec from `ai-sdk.dev/docs/ai-sdk-ui/stream-protocol`
and implemented it against LiteLLM's OpenAI-shape stream. Three divergences
surfaced when compared against Vercel's own reference template
(`vercel-labs/ai-sdk-preview-python-streaming`):

1. **`message_id` is fragile.** We do
   `getattr(chunk, "id", None) or "msg_unknown"` in
   `litellm_provider.py:67`. Anthropic-native chunks don't carry `.id`; any
   future `AnthropicNativeProvider` would emit `msg_unknown` to the
   frontend, breaking UI rendering that depends on a stable per-message id.
2. **`text-*` events use the wrong `id` field.** `events.py:43,46,49`
   pass `message_id` as the `id` of `text-start` / `text-delta` / `text-end`.
   The spec requires a per-part content id (e.g. `text-1`) that is stable
   across the three events of one text part. The frontend's `useChat()`
   matches deltas to a text part by `id`; using the message id collides
   across text parts in the same message.
3. **No token usage emitted.** We never populate
   `messageMetadata.usage.{prompt,completion,total}Tokens` on the `finish`
   event. The frontend can't display "this response used X tokens"; ops
   can't reconcile billing per request without correlating server logs.

The template also shows patterns we explicitly reject: hardcoded `gpt-4o`,
a monolithic single-turn `stream_text` that does dispatch inline, a bare
`except Exception` with `traceback.print_exc()` + re-raise. We keep our
separation (`provider.py` → `service.py` → `events.py`) and typed error
codes.

## Decision

Adopt three patterns from the template. Skip the rest as YAGNI.

### Adopt

**Fix 1 — `message_id` from `uuid4` upfront.**
In `litellm_provider.py`, generate `message_id = f"msg-{uuid.uuid4().hex}"`
at the top of `stream()`, emit `MESSAGE_START` immediately, and ignore
`chunk.id`. This makes the contract uniform across LiteLLM, future
Anthropic native, and any stub provider used in tests.

**Fix 2 — text part id, not message id, in `text-*` events.**
In `events.py`, add a module constant `TEXT_PART_ID = "text-1"`. Use it
as the `id` field of `text-start`, `text-delta`, and `text-end`. The
`messageId` field on the `start` event is unaffected.

We currently emit only one text part per turn, so the constant is fine.
If we ever need parallel text parts (e.g. reasoning + answer), revisit
and allocate per-part ids from the service layer.

**Fix 3 — emit `messageMetadata.usage` on `finish`.**
Extend `LLMEvent` with `usage: dict[str, int] | None = None`. In
`litellm_provider.py`, capture `chunk.usage` from the last chunk
(LiteLLM puts it on the final chunk for both OpenAI and Anthropic), and
attach it to the `MESSAGE_FINISH` event. In `events.py`, when
`event.usage` is set, emit
`{"type": "finish", "finishReason": ..., "messageMetadata": {"usage": event.usage}}`.

The usage dict shape (matches the Vercel spec):

```python
{"promptTokens": int, "completionTokens": int, "totalTokens": int}
```

Omit any key the provider didn't report.

### Reject (with reason)

- **`convert_to_openai_messages`-style rich input adapter.** Handles
  `parts` (text, image, file), `experimental_attachments`,
  `toolInvocations` with state. Our `ChatRequest` (ADR-0015) accepts
  `{role, content}` only. Vision and attachments are not on the roadmap;
  rebuild when there's a real consumer, not before.
- **`protocol=data` query param.** Template offers a runtime switch
  between the legacy "data" stream and the new "ui-message-stream". We
  closed on `ui-message-stream` only. Adding a switch is surface area
  with no user.
- **`traceback.print_exc()` in the stream generator.** Template's only
  recovery for any exception is "log and re-raise". We carry typed
  `LLMError` codes (`upstream`, `tool`, `timeout`, `loop`) through to
  the SSE `error` event so the frontend can show a meaningful message.
  Keeping our typed path; adding a `traceback` log line in service.py's
  outermost `except Exception` is the only borrow, and it's optional.
- **Single-turn dispatch inside `stream_text`.** The template is one
  LLM call → done. We have an agentic loop (ADR-0014, max 8 iterations)
  that needs its own dispatch step. The template's organization
  doesn't transfer.

## Files to change

| File                                                          | Change                                                                               |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| `backend/src/quaestor/chat/llm/provider.py`                   | `LLMEvent` gains `usage: dict \| None`.                                              |
| `backend/src/quaestor/chat/llm/litellm_provider.py`           | `message_id` from `uuid4`; capture `usage`; ignore `chunk.id`.                       |
| `backend/src/quaestor/chat/events.py`                         | `TEXT_PART_ID` constant; `text-*` use it; `finish` includes `messageMetadata.usage`. |
| `backend/src/quaestor/chat/service.py`                        | Pass `usage` from `MESSAGE_FINISH` provider event to the renderer.                   |
| `backend/tests/chat/test_litellm_provider.py` (new)           | 3 tests: uuid4, text part id, usage on finish.                                       |
| `docs/adr/0018-adopt-vercel-template-best-practices.md` (new) | Mirror of this spec, ADR-style.                                                      |
| `docs/adr/README.md`                                          | Add row for 0018.                                                                    |

## Tests

Three regression tests, one per fix, all using stubbed async iterators
(no network):

1. `test_message_id_is_uuid4_not_msg_unknown` — feed a chunk with no
   `.id`; assert the emitted `MESSAGE_START` has `messageId` matching
   `r"^msg-[0-9a-f]{32}$"`.
2. `test_text_events_use_text_part_id_not_message_id` — assert
   `text-start` / `text-delta` / `text-end` all carry `id == "text-1"`,
   and that the `id` differs from the `start` event's `messageId`.
3. `test_finish_event_includes_usage_metadata` — feed a final chunk
   with `usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5,
total_tokens=15)`; assert the rendered SSE has
   `messageMetadata.usage = {promptTokens: 10, completionTokens: 5,
totalTokens: 15}`.

Plus: existing tests in `test_service.py` should pass unchanged
(LLMEvent additions are additive; the new `usage` field is `None` when
not set).

## Risks

- **Fix 2 is technically a wire-format change** for the `id` of
  `text-*` events. The frontend uses `useChat()` from the Vercel SDK,
  which expects the spec-correct per-part id. A frontend that had been
  silently relying on the wrong id (matching by message_id) would break.
  We verified: no Quaestor frontend code reads `id` from text events
  directly. `useChat()` itself expects the spec-correct shape. Risk:
  effectively zero.
- **Fix 3 depends on `chunk.usage`.** If a provider behind LiteLLM
  doesn't normalize usage, `getattr(chunk, "usage", None)` returns
  `None` and the `messageMetadata` is omitted. The `finish` event still
  emits. No breakage.
- **Fix 1 is a pure refactor.** The wire format's `messageId` changes
  from "whatever the chunk said, or `msg_unknown`" to "a fresh
  uuid4 on every stream". Frontend treats it as an opaque id. No
  consumer cares about the value, only that it's stable for the
  duration of the message.

## Consequences

- One new dep: none.
- One new env var: none.
- One new ADR: 0018.
- Three new tests, no test deletions.
- Wire format gains one optional field (`messageMetadata.usage`) and
  one corrected field (`text-*.id`). Both are forward-compatible.
- Future `AnthropicNativeProvider` gets the message-id strategy for
  free; the provider interface stays the same.

## Out of scope (revisit later)

- Rich input adapter (parts, attachments, vision).
- Multi-part text streams (parallel reasoning + answer).
- Protocol switch query param.
- Per-tool-call start-step / finish-step events (we currently emit
  `finish-step` once per LLM round-trip; Vercel may want one per
  individual tool call — verify with a real conversation first).
