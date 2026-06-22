import pytest

from quaestor.chat.llm.factory import build_llm_provider
from quaestor.chat.llm.litellm_provider import LiteLLMProvider
from quaestor.chat.llm.provider import LLMProvider


def test_default_provider_is_litellm(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    provider = build_llm_provider()
    assert isinstance(provider, LiteLLMProvider)


def test_provider_is_llmprovider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "litellm")
    monkeypatch.setenv("LLM_MODEL", "anthropic/MiniMax-M3")
    provider = build_llm_provider()
    assert isinstance(provider, LLMProvider)


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "magic-llm")
    with pytest.raises(ValueError, match="litellm"):
        build_llm_provider()
