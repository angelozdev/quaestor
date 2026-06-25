"""API-level coverage for the `CHAT_SYSTEM_PROMPT` env var (ADR-0017).

Drives `POST /api/chat` end-to-end via the `app` fixture and asserts that
the conversation list the upstream provider actually receives reflects the
resolved system prompt (default / literal / truncated / disabled).
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from quaestor.chat.llm.provider import LLMEvent, LLMEventType, LLMProvider


class CapturingProvider(LLMProvider):
    """Records every `messages` list the route hands to the provider."""

    def __init__(self) -> None:
        self.calls: list[list[dict[str, Any]]] = []

    async def stream(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> AsyncIterator[LLMEvent]:
        self.calls.append(list(messages))
        yield LLMEvent(type=LLMEventType.MESSAGE_START, message_id="m")
        yield LLMEvent(
            type=LLMEventType.MESSAGE_FINISH, stop_reason="stop", iterations=1
        )


@pytest.fixture
def capturing_app(monkeypatch, engine):
    """A TestClient app whose LLM provider captures the messages it sees."""
    from quaestor.api.deps import require_auth

    cap = CapturingProvider()
    monkeypatch.setattr("quaestor.chat.llm.factory.build_llm_provider", lambda: cap)
    monkeypatch.setattr("quaestor.api.chat.build_llm_provider", lambda: cap)
    from quaestor.api import create_app

    app = create_app()
    app.dependency_overrides[require_auth] = lambda: None
    return app, cap


def _post_chat(client: TestClient, msg: str = "hola") -> None:
    with client.stream(
        "POST",
        "/api/chat",
        json={"messages": [{"role": "user", "content": msg}]},
    ) as r:
        assert r.status_code == 200
        # drain
        for _ in r.iter_bytes():
            pass


def test_default_env_value_injects_bundled_coach_prompt(monkeypatch, capturing_app):
    """Setting `CHAT_SYSTEM_PROMPT=default` → the bundled coach prompt is
    prepended; the user's message follows."""
    monkeypatch.setenv("CHAT_SYSTEM_PROMPT", "default")
    app, cap = capturing_app
    client = TestClient(app)

    _post_chat(client)

    assert cap.calls, "provider never called"
    msgs = cap.calls[0]
    assert msgs[0]["role"] == "system"
    assert "coach financiero" in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "hola"}


def test_literal_env_value_injected_verbatim(monkeypatch, capturing_app):
    """Any non-sentinel value is used verbatim (within the 4 k cap)."""
    monkeypatch.setenv("CHAT_SYSTEM_PROMPT", "Eres un loro.")
    app, cap = capturing_app
    client = TestClient(app)

    _post_chat(client)

    msgs = cap.calls[0]
    assert msgs[0] == {"role": "system", "content": "Eres un loro."}


def test_unset_env_means_no_injection(monkeypatch, capturing_app):
    """Unset env → back-compat: messages reach the provider untouched."""
    monkeypatch.delenv("CHAT_SYSTEM_PROMPT", raising=False)
    app, cap = capturing_app
    client = TestClient(app)

    _post_chat(client)

    msgs = cap.calls[0]
    assert msgs == [{"role": "user", "content": "hola"}]
    assert not any(m["role"] == "system" for m in msgs)


def test_off_sentinel_disables_injection(monkeypatch, capturing_app):
    """Some deploy systems can only override envs, not unset them.
    Setting the value to `off` (case-insensitive) is the disable knob."""
    monkeypatch.setenv("CHAT_SYSTEM_PROMPT", "off")
    app, cap = capturing_app
    client = TestClient(app)

    _post_chat(client)

    assert not any(m["role"] == "system" for m in cap.calls[0])


def test_oversize_prompt_truncated_at_4k(monkeypatch, capturing_app, caplog):
    """Defensive ceiling: an oversized prompt is truncated and a warning is
    logged so operators notice the misconfiguration."""
    monster = "x" * 10_000
    monkeypatch.setenv("CHAT_SYSTEM_PROMPT", monster)
    app, cap = capturing_app
    client = TestClient(app)

    with caplog.at_level("WARNING"):
        _post_chat(client)

    injected = cap.calls[0][0]["content"]
    assert len(injected) == 4_000
    assert any(
        "truncating" in rec.message.lower() for rec in caplog.records
    ), "expected a truncation warning log"


def test_blank_env_means_no_injection(monkeypatch, capturing_app):
    """Whitespace-only is treated as unset."""
    monkeypatch.setenv("CHAT_SYSTEM_PROMPT", "   ")
    app, cap = capturing_app
    client = TestClient(app)

    _post_chat(client)

    assert not any(m["role"] == "system" for m in cap.calls[0])
