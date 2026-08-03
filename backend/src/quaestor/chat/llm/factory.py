"""LLMProvider factory — select the active provider from `LLM_PROVIDER`."""

from __future__ import annotations

import os

from .litellm_provider import LiteLLMProvider
from .provider import LLMProvider

_RECOGNIZED = {"litellm": LiteLLMProvider}


def build_llm_provider() -> LLMProvider:
    """Return the configured LLMProvider. Fails fast on unknown values."""
    name = os.environ.get("LLM_PROVIDER", "litellm").strip().lower() or "litellm"
    cls = _RECOGNIZED.get(name)
    if cls is None:
        raise ValueError(f"Unknown LLM_PROVIDER={name!r}. Recognized values: {sorted(_RECOGNIZED)}")
    return cls(
        model=os.environ.get("LLM_MODEL", "anthropic/MiniMax-M3"),
        api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        base_url=os.environ.get("ANTHROPIC_BASE_URL") or None,
    )
