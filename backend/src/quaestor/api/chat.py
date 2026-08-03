"""`POST /api/chat` — natural-language HTTP bridge to MCP.

Returns an SSE stream that conforms to the Vercel AI SDK UI Message Stream
protocol (`x-vercel-ai-ui-message-stream: v1`). Frontend consumes via
`useChat()` + `DefaultChatTransport({ api: '/api/chat' })`.

Request validation:
  - max 200 messages
  - max 32 KB per message content
  - rough token estimate = `sum(len(content)) // 4` must not exceed 100_000

Per-call timeout:
  - `CHAT_REQUEST_TIMEOUT_S` (default 120) bounds each upstream `provider.stream`
    call AND each MCP `call_tool` invocation. Enforced via `asyncio.wait_for`
    inside `ChatService.stream` so the abort is observable to the SSE consumer
    (emits a `tool-output-available` with `is_error=true` for tool timeouts,
    and an `error` event with `code="timeout"` for provider timeouts).
"""

from __future__ import annotations

import logging
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..chat.llm.factory import build_llm_provider
from ..chat.prompts import COACH_SYSTEM_PROMPT
from ..chat.service import ChatService
from ..mcp.builder import build_mcp
from .deps import require_auth

router = APIRouter(prefix="/chat", tags=["chat"])

_MAX_MESSAGES = 200
_MAX_MESSAGE_BYTES = 32 * 1024
_MAX_TOKEN_ESTIMATE = 100_000

# ADR-0017: the system-prompt ceiling. Set from `CHAT_SYSTEM_PROMPT` env var;
# 4 000 chars ≈ 1 k tokens, well inside the 100 k request budget.
_SYSTEM_PROMPT_MAX_CHARS = 4_000
# Sentinel that disables the persona without forcing operators to unset the
# var (some deploy systems can't un-set, only override). Empty string = off.
_DISABLE_SENTINEL = "off"

Role = Literal["user", "assistant", "tool", "system"]


class ChatMessage(BaseModel):
    role: Role
    content: str = ""


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


def _validate_limits(req: ChatRequest) -> None:
    if len(req.messages) > _MAX_MESSAGES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="too many messages (max 200)",
        )
    for m in req.messages:
        if len(m.content) > _MAX_MESSAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="message content exceeds 32 KB",
            )
    total_chars = sum(len(m.content) for m in req.messages)
    if total_chars // 4 > _MAX_TOKEN_ESTIMATE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="request token estimate exceeds 100k",
        )


def _resolve_system_prompt() -> str | None:
    """Read `CHAT_SYSTEM_PROMPT` from env and decide whether to inject.

    Resolution rules (ADR-0017):
      - Unset / empty / "off" → no injection (back-compat with pre-ADR-0017).
      - Set to the literal string "default" → use the bundled coach prompt.
      - Set to anything else → use that string verbatim, truncated to
        `_SYSTEM_PROMPT_MAX_CHARS` with a warning log if exceeded.
    """
    raw = os.environ.get("CHAT_SYSTEM_PROMPT", "").strip()
    if not raw or raw.lower() == _DISABLE_SENTINEL:
        return None
    if raw.lower() == "default":
        return COACH_SYSTEM_PROMPT
    if len(raw) > _SYSTEM_PROMPT_MAX_CHARS:
        logging.getLogger(__name__).warning(
            "CHAT_SYSTEM_PROMPT is %d chars; truncating to %d",
            len(raw),
            _SYSTEM_PROMPT_MAX_CHARS,
        )
        return raw[:_SYSTEM_PROMPT_MAX_CHARS]
    return raw


@router.post("", dependencies=[Depends(require_auth)])
async def chat(req: ChatRequest) -> StreamingResponse:
    _validate_limits(req)

    provider = build_llm_provider()
    mcp = build_mcp()
    max_iterations = int(os.environ.get("CHAT_MAX_ITERATIONS", "8"))
    timeout_s = float(os.environ.get("CHAT_REQUEST_TIMEOUT_S", "120"))
    system_prompt = _resolve_system_prompt()
    service = ChatService(
        provider=provider,
        mcp=mcp,
        max_iterations=max_iterations,
        request_timeout_s=timeout_s,
        system_prompt=system_prompt,
    )

    messages_payload = [m.model_dump() for m in req.messages]
    generator = service.stream(messages_payload)

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "x-vercel-ai-ui-message-stream": "v1",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
