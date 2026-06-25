# Adopt Vercel Template Best Practices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three SSE wire-format bugs in the Quaestor chat endpoint by adopting patterns from `vercel-labs/ai-sdk-preview-python-streaming` (the only authoritative Python reference for the Vercel UI Message Stream protocol).

**Architecture:** TDD per fix. Each fix has its own task with a failing test, minimal impl, and commit. Last task wires docs. No new deps, no new env vars, no frontend changes.

**Tech Stack:** Python 3.12, LiteLLM, FastAPI, Pydantic, pytest + pytest-asyncio.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-06-23-vercel-template-best-practices-design.md`
- **Code language:** English (ADR-0001). Comments and identifiers in English; user-facing copy in Spanish.
- **ADRs:** any new technical decision recorded as `docs/adr/NNNN-slug.md` via the `adr` skill.
- **Wire format authority:** Vercel UI Message Stream (`x-vercel-ai-ui-message-stream: v1`). The frontend's `useChat()` parses it; never emit anything outside this enum.
- **Test framework:** `pytest -q` from `backend/` directory; tests live in `backend/tests/chat/`.
- **Run tests:** `cd backend && uv run pytest tests/chat -q`.
- **Lint:** `cd backend && uv run ruff check src tests` (matches pyproject.toml).
- **Commit style:** `type(scope): summary` (Conventional Commits, as in recent history).

---

## Task 1: Fix 1 — `message_id` from `uuid4` upfront (no `msg_unknown`)

**Files:**
- Modify: `backend/src/quaestor/chat/llm/litellm_provider.py`
- Test: `backend/tests/chat/test_litellm_provider.py`

**Interfaces:**
- Consumes: `litellm.acompletion(...)` async iterator of chunks (chunk shape unchanged).
- Produces: `LiteLLMProvider.stream(...)` async iterator yielding `LLMEvent`s. The very first yielded event is `LLMEventType.MESSAGE_START` with `message_id` matching `r"^msg-[0-9a-f]{32}$"`.

### Steps

- [ ] **Step 1: Add the failing test**

Append to `backend/tests/chat/test_litellm_provider.py`:

```python
@pytest.mark.asyncio
async def test_message_id_is_uuid4_not_msg_unknown():
    """Per the Vercel UI Message Stream spec, messageId is an opaque
    identifier for the whole message. Generate it locally with uuid4 so it
    works even when the upstream chunk lacks `.id` (Anthropic native).
    """
    import re

    chunks = [
        # Deliberately NO `id` field on the chunk — simulates Anthropic.
        _chunk(content="Hola"),
        _chunk(content=None, finish_reason="stop"),
    ]

    async def fake_acompletion(**kwargs):
        for c in chunks:
            yield c

    with patch("litellm.acompletion", side_effect=fake_acompletion):
        provider = LiteLLMProvider(model="anthropic/MiniMax-M3", api_key="x", base_url=None)
        events = await _collect(
            provider.stream(messages=[{"role": "user", "content": "hola"}], tools=[])
        )

    starts = [e for e in events if e.type == LLMEventType.MESSAGE_START]
    assert len(starts) == 1, f"expected exactly one MESSAGE_START, got {len(starts)}"
    assert starts[0].message_id is not None
    assert re.fullmatch(r"msg-[0-9a-f]{32}", starts[0].message_id), (
        f"message_id should be 'msg-<32 hex chars>', got {starts[0].message_id!r}"
    )
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
cd backend && uv run pytest tests/chat/test_litellm_provider.py::test_message_id_is_uuid4_not_msg_unknown -q
```
Expected: FAIL with `AssertionError` (current code sets `message_id = "msg_test_1"` from `chunk.id` or falls back to `"msg_unknown"` — neither matches the uuid4 regex).

- [ ] **Step 3: Implement uuid4 + emit MESSAGE_START before the first chunk**

In `backend/src/quaestor/chat/llm/litellm_provider.py`, replace the import block (top of file) to add `uuid`:

Current imports (top of file):
```python
from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import litellm
```

Replace with:
```python
from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncIterator
from typing import Any

import litellm
```

In the `stream` method, replace the local-state initialization block (the lines just before `try: response = await litellm.acompletion(...)`):

Current code:
```python
        # Track per-tool-call state across chunks.
        # accumulated[idx] = {"id": str|None, "name": str|None, "args_buf": str, "started": bool}
        accumulated: dict[int, dict[str, Any]] = {}
        message_id: str | None = None
        text_started = False

        try:
            response = await litellm.acompletion(**kwargs)
        except _LITELLM_UPSTREAM_ERRORS as exc:
            raise UpstreamLLMError(str(exc)) from exc

        try:
            async for chunk in response:
                if message_id is None:
                    message_id = getattr(chunk, "id", None) or "msg_unknown"
                    yield LLMEvent(
                        type=LLMEventType.MESSAGE_START,
                        message_id=message_id,
                        model=self._model,
                    )
```

Replace with:
```python
        # Track per-tool-call state across chunks.
        # accumulated[idx] = {"id": str|None, "name": str|None, "args_buf": str, "started": bool}
        accumulated: dict[int, dict[str, Any]] = {}
        text_started = False

        # Vercel UI Message Stream spec: `messageId` is the opaque identifier
        # of the whole message. Generate it locally with uuid4 so the value
        # is uniform regardless of whether the upstream provider attaches
        # `.id` to chunks (OpenAI does, Anthropic native does not).
        message_id = f"msg-{uuid.uuid4().hex}"

        try:
            response = await litellm.acompletion(**kwargs)
        except _LITELLM_UPSTREAM_ERRORS as exc:
            raise UpstreamLLMError(str(exc)) from exc

        try:
            yield LLMEvent(
                type=LLMEventType.MESSAGE_START,
                message_id=message_id,
                model=self._model,
            )
            async for chunk in response:
                choice = chunk.choices[0]
                delta = choice.delta

                # --- text streaming ---------------------------------------------
                content_piece: str | None = getattr(delta, "content", None)
                if content_piece:
                    if not text_started:
                        text_started = True
                        yield LLMEvent(type=LLMEventType.TEXT_START, content_index=0)
                    yield LLMEvent(type=LLMEventType.TEXT_DELTA, delta=content_piece)

- [ ] **Step 4: Run the test to confirm it passes**

Run:
```bash
cd backend && uv run pytest tests/chat/test_litellm_provider.py::test_message_id_is_uuid4_not_msg_unknown -q
```
Expected: PASS.

- [ ] **Step 5: Run the full chat test suite to check for regressions**

Run:
```bash
cd backend && uv run pytest tests/chat -q
```
Expected: all green. The `_chunk()` helper in existing tests still sets `id="msg_test_1"` on each chunk, but that value is now ignored — only `uuid4` is used.

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/chat/llm/litellm_provider.py backend/tests/chat/test_litellm_provider.py
git commit -m "fix(chat): use uuid4 message_id upfront, ignore chunk.id

Anthropic-native chunks don't carry `.id`; the previous fallback
to 'msg_unknown' would break any future AnthropicNativeProvider.
Generate a fresh uuid4 hex per stream so the value is uniform across
LiteLLM, future Anthropic native, and stub providers in tests."
```

---

## Task 2: Fix 2 — text part id (not message_id) on `text-*` events

**Files:**
- Modify: `backend/src/quaestor/chat/events.py`
- Modify: `backend/tests/chat/test_events.py` (existing assertions on `id == "m"` must update)

**Interfaces:**
- Consumes: `LLMEvent(type=TEXT_START | TEXT_DELTA | TEXT_END, ...)`.
- Produces: SSE bytes whose JSON has `id == "text-1"` (per-part content id per the Vercel spec), NOT the `messageId` of the parent message.

### Steps

- [ ] **Step 1: Update the existing tests in `test_events.py`**

In `backend/tests/chat/test_events.py`, replace the three existing tests with versions that assert the spec-correct behavior. Replace the whole block from `def test_serialize_text_delta():` through `def test_serialize_text_start_and_end_share_content_index():` (those two test functions) with:

```python
def test_serialize_text_delta_uses_text_part_id_not_message_id():
    """The `id` of a text-* event is the per-part content id (`text-1`),
    NOT the message id. Per the Vercel UI Message Stream spec, useChat()
    matches deltas to a part by id."""
    ev = LLMEvent(type=LLMEventType.TEXT_DELTA, delta="hola")
    out = _data(serialize_event(ev, message_id="msg_abc"))
    assert out == {"type": "text-delta", "id": "text-1", "delta": "hola"}
    assert out["id"] != out["messageId"] if "messageId" in out else True
    # The "id" must NOT equal the message id we passed in.
    assert out["id"] != "msg_abc"


def test_serialize_text_start_and_end_share_text_part_id():
    start = _data(serialize_event(LLMEvent(type=LLMEventType.TEXT_START, content_index=0), message_id="msg_abc"))
    delta = _data(serialize_event(LLMEvent(type=LLMEventType.TEXT_DELTA, content_index=0, delta="x"), message_id="msg_abc"))
    end = _data(serialize_event(LLMEvent(type=LLMEventType.TEXT_END, content_index=0), message_id="msg_abc"))
    assert start == {"type": "text-start", "id": "text-1"}
    assert delta["id"] == "text-1"
    assert end == {"type": "text-end", "id": "text-1"}
    # None of them carry the message id.
    for ev in (start, delta, end):
        assert ev["id"] != "msg_abc"
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run:
```bash
cd backend && uv run pytest tests/chat/test_events.py::test_serialize_text_delta_uses_text_part_id_not_message_id tests/chat/test_events.py::test_serialize_text_start_and_end_share_text_part_id -q
```
Expected: both FAIL with `AssertionError` on the `id` value (current code emits `"id": "msg_abc"`).

- [ ] **Step 3: Add `TEXT_PART_ID` constant and update the three text-* branches in `events.py`**

In `backend/src/quaestor/chat/events.py`, add the constant near the top (after the `render_sse` and `done_bytes` helpers, before `serialize_event`):

Current code (after `done_bytes`):
```python
def done_bytes() -> bytes:
    """The literal `[DONE]` sentinel Vercel's parser uses to end a stream."""
    return b"data: [DONE]\n\n"


def serialize_event(event: LLMEvent, *, message_id: str) -> bytes:
```

Replace with:
```python
def done_bytes() -> bytes:
    """The literal `[DONE]` sentinel Vercel's parser uses to end a stream."""
    return b"data: [DONE]\n\n"


# Per the Vercel UI Message Stream spec, the `id` of a text-* event is a
# per-part content id (stable across text-start/text-delta/text-end of the
# same text part). It must NOT collide with `messageId`. We currently emit
# exactly one text part per turn, so a constant suffices; revisit when we
# add parallel parts (e.g. reasoning + answer).
TEXT_PART_ID = "text-1"


def serialize_event(event: LLMEvent, *, message_id: str) -> bytes:
```

Now replace the three text-* branches inside `serialize_event`. Current code:

```python
    if t == LLMEventType.TEXT_START:
        return render_sse({"type": "text-start", "id": message_id})

    if t == LLMEventType.TEXT_DELTA:
        return render_sse({"type": "text-delta", "id": message_id, "delta": event.delta or ""})

    if t == LLMEventType.TEXT_END:
        return render_sse({"type": "text-end", "id": message_id})
```

Replace with:

```python
    if t == LLMEventType.TEXT_START:
        return render_sse({"type": "text-start", "id": TEXT_PART_ID})

    if t == LLMEventType.TEXT_DELTA:
        return render_sse({"type": "text-delta", "id": TEXT_PART_ID, "delta": event.delta or ""})

    if t == LLMEventType.TEXT_END:
        return render_sse({"type": "text-end", "id": TEXT_PART_ID})
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run:
```bash
cd backend && uv run pytest tests/chat/test_events.py -q
```
Expected: all green.

- [ ] **Step 5: Run the full chat test suite to check for regressions**

Run:
```bash
cd backend && uv run pytest tests/chat -q
```
Expected: all green. The existing `test_service.py` SSE-shape assertions don't pin the text `id` value to the message id, so they remain correct.

- [ ] **Step 6: Commit**

```bash
git add backend/src/quaestor/chat/events.py backend/tests/chat/test_events.py
git commit -m "fix(chat): use per-part text id 'text-1' on text-* events

The Vercel UI Message Stream spec requires the `id` of text-* events
to be a per-part content id, stable across text-start/text-delta/
text-end of the same part. The previous code reused the message id,
which would collide across parallel text parts. Single text part per
turn → constant 'text-1' is sufficient."
```

---

## Task 3: Fix 3 — emit `messageMetadata.usage` on `finish`

**Files:**
- Modify: `backend/src/quaestor/chat/llm/provider.py` (add `usage` field to `LLMEvent`).
- Modify: `backend/src/quaestor/chat/llm/litellm_provider.py` (capture `chunk.usage` and attach to `MESSAGE_FINISH`).
- Modify: `backend/src/quaestor/chat/events.py` (render `messageMetadata.usage` when set).
- Modify: `backend/tests/chat/test_events.py` (one new test for the renderer).
- Modify: `backend/tests/chat/test_litellm_provider.py` (one new test for the provider capture path).

**Interfaces:**
- Consumes: LiteLLM chunks whose final chunk carries `.usage` with attributes `prompt_tokens`, `completion_tokens`, optional `total_tokens`.
- Produces: `LLMEvent(type=MESSAGE_FINISH, usage={"promptTokens": int, "completionTokens": int, "totalTokens": int})` (omit any missing key).
- Wire: SSE `{"type": "finish", "finishReason": "...", "messageMetadata": {"usage": {...}}}` when `usage` is set; else the previous 2-field shape.

### Steps

- [ ] **Step 1: Add `usage` field to `LLMEvent` dataclass**

In `backend/src/quaestor/chat/llm/provider.py`, in the `LLMEvent` dataclass, add one field. Current code (just before the closing of `LLMEvent`):

```python
    # message-level
    message_id: str | None = None
    model: str | None = None
    stop_reason: str | None = None
    iterations: int | None = None
```

Replace with:

```python
    # message-level
    message_id: str | None = None
    model: str | None = None
    stop_reason: str | None = None
    iterations: int | None = None
    # Token usage, normalized to Vercel wire keys. `None` = provider didn't
    # report; renderer omits `messageMetadata` in that case.
    # Shape: {"promptTokens": int, "completionTokens": int, "totalTokens": int}
    usage: dict[str, int] | None = None
```

- [ ] **Step 2: Add a failing renderer test in `test_events.py`**

Append to `backend/tests/chat/test_events.py`:

```python
def test_serialize_message_finish_with_usage_includes_message_metadata():
    """When usage is present, emit messageMetadata.usage on the finish event
    so the frontend can display token counts and ops can reconcile billing."""
    ev = LLMEvent(
        type=LLMEventType.MESSAGE_FINISH,
        stop_reason="stop",
        iterations=1,
        usage={"promptTokens": 10, "completionTokens": 5, "totalTokens": 15},
    )
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {
        "type": "finish",
        "finishReason": "stop",
        "messageMetadata": {"usage": {"promptTokens": 10, "completionTokens": 5, "totalTokens": 15}},
    }


def test_serialize_message_finish_without_usage_omits_message_metadata():
    """When usage is None (provider didn't report), the wire shape is unchanged
    from before this fix — additive, not breaking."""
    ev = LLMEvent(type=LLMEventType.MESSAGE_FINISH, stop_reason="stop", iterations=1)
    out = _data(serialize_event(ev, message_id="m"))
    assert out == {"type": "finish", "finishReason": "stop"}
    assert "messageMetadata" not in out
```

- [ ] **Step 3: Run the new tests to confirm the second passes and the first fails**

Run:
```bash
cd backend && uv run pytest tests/chat/test_events.py::test_serialize_message_finish_with_usage_includes_message_metadata tests/chat/test_events.py::test_serialize_message_finish_without_usage_omits_message_metadata -q
```
Expected: the second passes, the first FAILS (no `messageMetadata` in output yet).

- [ ] **Step 4: Render `messageMetadata.usage` in `events.py`**

In `backend/src/quaestor/chat/events.py`, update the `MESSAGE_FINISH` branch. Current code:

```python
    if t == LLMEventType.MESSAGE_FINISH:
        # Renderer is dumb by design: the LLMProvider maps provider-specific
        # finish_reason to the Vercel spec enum (`stop | length | content-filter
        # | tool-calls | error | other`). Defaulting to "stop" covers the rare
        # case where a scripted test or stub provider doesn't set it.
        return render_sse({"type": "finish", "finishReason": event.stop_reason or "stop"})
```

Replace with:

```python
    if t == LLMEventType.MESSAGE_FINISH:
        # Renderer is dumb by design: the LLMProvider maps provider-specific
        # finish_reason to the Vercel spec enum (`stop | length | content-filter
        # | tool-calls | error | other`). Defaulting to "stop" covers the rare
        # case where a scripted test or stub provider doesn't set it.
        # `messageMetadata.usage` is omitted when the provider didn't report
        # usage (additive contract; never breaks older clients).
        payload: dict[str, Any] = {
            "type": "finish",
            "finishReason": event.stop_reason or "stop",
        }
        if event.usage:
            payload["messageMetadata"] = {"usage": event.usage}
        return render_sse(payload)
```

- [ ] **Step 5: Re-run the renderer tests**

Run:
```bash
cd backend && uv run pytest tests/chat/test_events.py -q
```
Expected: all green.

- [ ] **Step 6: Add a failing provider test for `usage` capture**

Append to `backend/tests/chat/test_litellm_provider.py`:

```python
@pytest.mark.asyncio
async def test_message_finish_carries_usage_from_final_chunk():
    """LiteLLM puts usage on the final chunk for both OpenAI and Anthropic.
    Capture it and attach to MESSAGE_FINISH so the renderer can emit
    messageMetadata.usage on the wire."""
    from types import SimpleNamespace

    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    chunks = [
        _chunk(content="ok"),
        SimpleNamespace(
            choices=[SimpleNamespace(index=0, delta=SimpleNamespace(), finish_reason="stop")],
            usage=usage,
        ),
    ]

    async def fake_acompletion(**kwargs):
        for c in chunks:
            yield c

    with patch("litellm.acompletion", side_effect=fake_acompletion):
        provider = LiteLLMProvider(model="anthropic/MiniMax-M3", api_key="x", base_url=None)
        events = await _collect(
            provider.stream(messages=[{"role": "user", "content": "hola"}], tools=[])
        )

    finishes = [e for e in events if e.type == LLMEventType.MESSAGE_FINISH]
    assert len(finishes) == 1
    assert finishes[0].usage == {
        "promptTokens": 10,
        "completionTokens": 5,
        "totalTokens": 15,
    }


@pytest.mark.asyncio
async def test_message_finish_usage_omits_missing_total_tokens():
    """Some providers report only prompt_tokens and completion_tokens."""
    from types import SimpleNamespace

    usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5)  # no total_tokens
    chunks = [
        _chunk(content="ok"),
        SimpleNamespace(
            choices=[SimpleNamespace(index=0, delta=SimpleNamespace(), finish_reason="stop")],
            usage=usage,
        ),
    ]

    async def fake_acompletion(**kwargs):
        for c in chunks:
            yield c

    with patch("litellm.acompletion", side_effect=fake_acompletion):
        provider = LiteLLMProvider(model="anthropic/MiniMax-M3", api_key="x", base_url=None)
        events = await _collect(
            provider.stream(messages=[{"role": "user", "content": "hola"}], tools=[])
        )

    finishes = [e for e in events if e.type == LLMEventType.MESSAGE_FINISH]
    assert finishes[0].usage == {"promptTokens": 10, "completionTokens": 5}


@pytest.mark.asyncio
async def test_message_finish_usage_none_when_provider_omits_it():
    """If no chunk carries usage, the MESSAGE_FINISH event has usage=None."""
    chunks = [
        _chunk(content="ok"),
        _chunk(content=None, finish_reason="stop"),  # no .usage
    ]

    async def fake_acompletion(**kwargs):
        for c in chunks:
            yield c

    with patch("litellm.acompletion", side_effect=fake_acompletion):
        provider = LiteLLMProvider(model="anthropic/MiniMax-M3", api_key="x", base_url=None)
        events = await _collect(
            provider.stream(messages=[{"role": "user", "content": "hola"}], tools=[])
        )

    finishes = [e for e in events if e.type == LLMEventType.MESSAGE_FINISH]
    assert finishes[0].usage is None
```

- [ ] **Step 7: Run the new provider tests to confirm they fail**

Run:
```bash
cd backend && uv run pytest tests/chat/test_litellm_provider.py::test_message_finish_carries_usage_from_final_chunk tests/chat/test_litellm_provider.py::test_message_finish_usage_omits_missing_total_tokens tests/chat/test_litellm_provider.py::test_message_finish_usage_none_when_provider_omits_it -q
```
Expected: all 3 FAIL with `AttributeError` or `AssertionError` (no `usage` capture yet).

- [ ] **Step 8: Capture usage and attach to `MESSAGE_FINISH` in `litellm_provider.py`**

In `backend/src/quaestor/chat/llm/litellm_provider.py`, two changes.

**Change A** — initialize `last_usage` in the local-state block. Current code (the block that begins `# Track per-tool-call state across chunks.`):

```python
        # Track per-tool-call state across chunks.
        # accumulated[idx] = {"id": str|None, "name": str|None, "args_buf": str, "started": bool}
        accumulated: dict[int, dict[str, Any]] = {}
        text_started = False
```

Replace with:

```python
        # Track per-tool-call state across chunks.
        # accumulated[idx] = {"id": str|None, "name": str|None, "args_buf": str, "started": bool}
        accumulated: dict[int, dict[str, Any]] = {}
        text_started = False
        # Token usage, captured from the last chunk that carries `.usage`.
        # Normalized to Vercel wire keys. None = provider didn't report.
        last_usage: dict[str, int] | None = None
```

**Change B** — capture `chunk.usage` inside the chunk loop and attach to `MESSAGE_FINISH`. Current code (inside the chunk loop, just after the `# --- finish reason:` block, before `yield LLMEvent(type=LLMEventType.STEP_FINISH)`):

```python
                # --- finish reason: flush tool calls / close text ---------------
                if choice.finish_reason:
                    if text_started:
                        yield LLMEvent(type=LLMEventType.TEXT_END, content_index=0)
                    for idx, slot in sorted(accumulated.items()):
                        # Parse accumulated arguments; if it's malformed JSON,
                        # surface it as an error rather than dropping the call.
                        try:
                            args_obj: Any = (
                                json.loads(slot["args_buf"]) if slot["args_buf"].strip() else {}
                            )
                        except json.JSONDecodeError as exc:
                            raise UpstreamLLMError(
                                f"tool_call {slot['id']} arguments not valid JSON: {exc}"
                            ) from exc
                        if not isinstance(args_obj, dict):
                            args_obj = {"value": args_obj}
                        yield LLMEvent(
                            type=LLMEventType.TOOL_INPUT_AVAILABLE,
                            tool_call_id=slot["id"],
                            tool_name=slot["name"] or "",
                            arguments=args_obj,
                        )
                    yield LLMEvent(type=LLMEventType.STEP_FINISH)
                    yield LLMEvent(
                        type=LLMEventType.MESSAGE_FINISH,
                        stop_reason=_to_vercel_finish_reason(choice.finish_reason),
                        iterations=1,
                    )
```

Replace with:

```python
                # --- finish reason: flush tool calls / close text ---------------
                if choice.finish_reason:
                    if text_started:
                        yield LLMEvent(type=LLMEventType.TEXT_END, content_index=0)
                    for idx, slot in sorted(accumulated.items()):
                        # Parse accumulated arguments; if it's malformed JSON,
                        # surface it as an error rather than dropping the call.
                        try:
                            args_obj: Any = (
                                json.loads(slot["args_buf"]) if slot["args_buf"].strip() else {}
                            )
                        except json.JSONDecodeError as exc:
                            raise UpstreamLLMError(
                                f"tool_call {slot['id']} arguments not valid JSON: {exc}"
                            ) from exc
                        if not isinstance(args_obj, dict):
                            args_obj = {"value": args_obj}
                        yield LLMEvent(
                            type=LLMEventType.TOOL_INPUT_AVAILABLE,
                            tool_call_id=slot["id"],
                            tool_name=slot["name"] or "",
                            arguments=args_obj,
                        )
                    yield LLMEvent(type=LLMEventType.STEP_FINISH)
                    yield LLMEvent(
                        type=LLMEventType.MESSAGE_FINISH,
                        stop_reason=_to_vercel_finish_reason(choice.finish_reason),
                        iterations=1,
                        usage=last_usage,
                    )
```

**Change C** — capture usage per chunk. Current code (the very first lines inside the `async for chunk in response:` loop, after Task 1 has been applied):

```python
            async for chunk in response:
                choice = chunk.choices[0]
                delta = choice.delta
```

Replace with:

```python
            async for chunk in response:
                # Capture token usage from any chunk that carries it. LiteLLM
                # normalizes usage onto the final chunk for both OpenAI and
                # Anthropic, but we accept it from any chunk in case other
                # providers stream it earlier. Last write wins.
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage is not None:
                    usage_payload: dict[str, int] = {}
                    prompt = getattr(chunk_usage, "prompt_tokens", None)
                    completion = getattr(chunk_usage, "completion_tokens", None)
                    total = getattr(chunk_usage, "total_tokens", None)
                    if prompt is not None:
                        usage_payload["promptTokens"] = prompt
                    if completion is not None:
                        usage_payload["completionTokens"] = completion
                    if total is not None:
                        usage_payload["totalTokens"] = total
                    if usage_payload:
                        last_usage = usage_payload

                choice = chunk.choices[0]
                delta = choice.delta
```

- [ ] **Step 9: Run the new provider tests to confirm they pass**

Run:
```bash
cd backend && uv run pytest tests/chat/test_litellm_provider.py::test_message_finish_carries_usage_from_final_chunk tests/chat/test_litellm_provider.py::test_message_finish_usage_omits_missing_total_tokens tests/chat/test_litellm_provider.py::test_message_finish_usage_none_when_provider_omits_it -q
```
Expected: all 3 PASS.

- [ ] **Step 10: Run the full chat test suite**

Run:
```bash
cd backend && uv run pytest tests/chat -q
```
Expected: all green. `test_service.py` SSE-shape assertions should pass — `usage` is `None` for stub providers, so the wire shape is unchanged for them.

- [ ] **Step 11: Commit**

```bash
git add backend/src/quaestor/chat/llm/provider.py backend/src/quaestor/chat/llm/litellm_provider.py backend/src/quaestor/chat/events.py backend/tests/chat/test_events.py backend/tests/chat/test_litellm_provider.py
git commit -m "feat(chat): emit messageMetadata.usage on finish event

Capture chunk.usage from LiteLLM's final chunk (works for OpenAI and
Anthropic). Normalize to Vercel wire keys (promptTokens /
completionTokens / totalTokens). Renderer emits messageMetadata.usage
only when usage is set — additive contract, older clients see no change."
```

---

## Task 4: ADR-0018 + README index row

**Files:**
- Create: `docs/adr/0018-adopt-vercel-template-best-practices.md`
- Modify: `docs/adr/README.md`

**Interfaces:** None — pure docs.

### Steps

- [ ] **Step 1: Scaffold the ADR (creates the file AND inserts a `proposed` row in the README index)**

Run:
```bash
cd /Users/angelozdev/me/quaestor && uv run .claude/skills/adr/scripts/new_adr.py "Adopt Vercel template best practices for chat SSE"
```
Expected: prints the new file path, something like `docs/adr/0018-adopt-vercel-template-best-practices.md`. The script also appends a `| 0018 | ... | proposed | 2026-06-24 |` row to `docs/adr/README.md`.

- [ ] **Step 2: Replace the ADR body with the canonical content**

The scaffold writes a generic template body. Open `docs/adr/0018-adopt-vercel-template-best-practices.md` and replace its entire body (everything after the H1 and frontmatter block) with:

```markdown

## Context

ADR-0014 shipped the chat endpoint by reverse-engineering the Vercel UI
Message Stream protocol from `ai-sdk.dev/docs`. Three divergences from
the Vercel-owned reference template
(`vercel-labs/ai-sdk-preview-python-streaming`) went unnoticed:

1. `message_id` came from `chunk.id` with a `msg_unknown` fallback.
   Anthropic-native chunks don't carry `.id`, so any future
   `AnthropicNativeProvider` would emit `msg_unknown` to the frontend.
2. `text-start` / `text-delta` / `text-end` events reused `message_id`
   as their `id`. The spec requires a per-part content id (e.g.
   `text-1`) so the frontend can match deltas to parts.
3. `finish` events never carried `messageMetadata.usage`, so the
   frontend can't show token counts and ops can't reconcile billing
   per request.

Full analysis lives in
`docs/superpowers/specs/2026-06-23-vercel-template-best-practices-design.md`.

## Decision

Adopt three patterns from the template. Keep our typed-error discipline
and `provider.py → service.py → events.py` separation. Skip the rich
input adapter (no vision / attachments on the roadmap), the
`protocol=data` query param (closed on `ui-message-stream`), and the
single-turn dispatch refactor (we have an agentic loop per ADR-0014).

## Consequences

- One new field on `LLMEvent`: `usage: dict[str, int] | None = None`.
- Wire format gains one optional field (`messageMetadata.usage`) and
  corrects one field (`text-*.id`). Both forward-compatible.
- Zero new deps, zero new env vars, zero frontend code changes.
- Three new tests, no deletions.
- Future `AnthropicNativeProvider` inherits the message-id strategy
  for free.

## Related

- ADR-0014 — chat endpoint base.
- ADR-0015 — frontend wire-format adapter.
- ADR-0016 — tool-error recovery (isError).
- ADR-0017 — system prompt injection.
- Spec: `docs/superpowers/specs/2026-06-23-vercel-template-best-practices-design.md`.
- Plan: `docs/superpowers/plans/2026-06-24-adopt-vercel-best-practices.md`.
```

- [ ] **Step 3: Update the README row's status from `proposed` → `accepted`**

In `docs/adr/README.md`, find the row the scaffold inserted (it has status `proposed`). Change it to `accepted`. The row should look like:

```
| 0018 | Adopt Vercel template best practices for chat SSE | accepted | 2026-06-24 |
```

- [ ] **Step 4: Commit**

```bash
git add docs/adr/0018-adopt-vercel-template-best-practices.md docs/adr/README.md
git commit -m "docs(adr): 0018 adopt Vercel template best practices for chat SSE

Three wire-format fixes (uuid4 message_id, text-* per-part id,
messageMetadata.usage) plus the rejected-pattern list with reasons.
Mirrors the design spec at
docs/superpowers/specs/2026-06-23-vercel-template-best-practices-design.md."
```

---

## Task 5: Final verification

**Files:** None.

**Interfaces:** None.

### Steps

- [ ] **Step 1: Run the entire backend test suite**

Run:
```bash
cd backend && uv run pytest -q
```
Expected: all green. Watch for any test outside `tests/chat/` that might exercise chat code paths indirectly (e.g. `test_api.py`).

- [ ] **Step 2: Run ruff**

Run:
```bash
cd backend && uv run ruff check src tests
```
Expected: clean (no warnings, no errors). If ruff reports style nits introduced by the new code (unused imports, etc.), fix them.

- [ ] **Step 3: Confirm zero new files in unexpected places**

Run:
```bash
git status --short
```
Expected output (untracked files from before this plan may still appear, that's fine):
```
M  backend/src/quaestor/chat/events.py
M  backend/src/quaestor/chat/llm/litellm_provider.py
M  backend/src/quaestor/chat/llm/provider.py
M  backend/tests/chat/test_events.py
M  backend/tests/chat/test_litellm_provider.py
M  docs/adr/0018-adopt-vercel-template-best-practices.md
M  docs/adr/README.md
```
(No `??` lines under `backend/` that aren't pre-existing.)

- [ ] **Step 4: Final commit if ruff or test cleanups touched anything**

If `git status` shows any new modifications from Steps 1–3:

```bash
git add -u
git commit -m "chore: lint + test cleanups from final verification"
```

If nothing changed, skip this step.

- [ ] **Step 5: Done**

Report the diff summary:
```bash
git log --oneline main..HEAD
```
Expected: 4 commits (Tasks 1, 2, 3, 4) + an optional 5th from Step 4.