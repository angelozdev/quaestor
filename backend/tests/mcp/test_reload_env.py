"""MCP_RELOAD env var drives uvicorn reload mode."""
from __future__ import annotations

from collections import OrderedDict

import pytest

from quaestor.mcp.server import _uvicorn_kwargs_from_env


def _env(**kwargs) -> "OrderedDict[str, str]":
    return OrderedDict(kwargs)


def test_defaults_match_production_behavior():
    """No MCP_RELOAD -> reload off, host/port from MCP_HOST/MCP_PORT or defaults."""
    env = _env(MCP_HOST="0.0.0.0", MCP_PORT="9000")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["factory"] is True
    assert kw["host"] == "0.0.0.0"
    assert kw["port"] == 9000
    assert kw["reload"] is False
    assert kw["reload_dirs"] is None


def test_mcp_reload_1_enables_reload():
    env = _env(MCP_RELOAD="1", MCP_HOST="0.0.0.0", MCP_PORT="9000")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["reload"] is True
    assert kw["reload_dirs"] == ["/app/src"]


def test_mcp_reload_true_enables_reload():
    env = _env(MCP_RELOAD="true")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["reload"] is True


def test_mcp_reload_yes_enables_reload():
    env = _env(MCP_RELOAD="yes")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["reload"] is True


def test_mcp_reload_zero_disables_reload():
    env = _env(MCP_RELOAD="0")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["reload"] is False


def test_mcp_reload_empty_string_disables_reload():
    env = _env(MCP_RELOAD="")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["reload"] is False


def test_mcp_reload_garbage_disables_reload():
    env = _env(MCP_RELOAD="maybe")
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["reload"] is False


def test_port_default_is_9000():
    env = _env()
    kw = _uvicorn_kwargs_from_env(env)
    assert kw["port"] == 9000
    assert kw["host"] == "0.0.0.0"


def test_port_invalid_raises_value_error():
    env = _env(MCP_PORT="not-a-number")
    with pytest.raises(ValueError):
        _uvicorn_kwargs_from_env(env)
