"""Hardening of SESSION_SECRET (QUA-A02-01).

Starlette signs the session cookie with `itsdangerous`. A short or default
secret makes cookie forgery trivial. We refuse to start without a
≥32-byte secret instead of falling back to a known-public default.
"""
from __future__ import annotations

import pytest
from quaestor.api import _resolve_session_secret


def test_missing_secret_raises(monkeypatch):
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        _resolve_session_secret()


def test_short_secret_raises(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "too-short")
    with pytest.raises(RuntimeError, match=r"≥32 bytes"):
        _resolve_session_secret()


def test_whitespace_only_secret_raises(monkeypatch):
    # Whitespace does not count — strip() must reject " " * 64.
    monkeypatch.setenv("SESSION_SECRET", "   ")
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        _resolve_session_secret()


def test_32_byte_secret_accepted(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "x" * 32)
    assert _resolve_session_secret() == "x" * 32


def test_long_secret_passes_through(monkeypatch):
    secret = "a-real-secret-from-secrets-token-urlsafe-64-bytes"
    monkeypatch.setenv("SESSION_SECRET", secret)
    assert _resolve_session_secret() == secret
