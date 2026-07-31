"""Step registry and scenario runner for the acceptance pipeline.

Handlers register themselves with the :func:`step` decorator. Matching is
anchored-regex over the step's exact text (regex is the project extension
over exact-text matching — amounts and names vary between steps).

A generated test calls :func:`run_scenario` with the literal steps from the
IR; every scenario gets a fresh :class:`World` (in-memory SQLite, migrated
via ``init_db``) from the generated ``conftest.py``'s ``world`` fixture.
"""
from __future__ import annotations

import re
from typing import Callable

from .world import World

# ---------------------------------------------------------------- registry

_REGISTRY: list[tuple[re.Pattern[str], Callable]] = []


def step(pattern: str) -> Callable[[Callable], Callable]:
    """Register a step handler under an anchored regex ``pattern``."""
    compiled = re.compile(r"\A" + pattern + r"\Z")

    def deco(fn: Callable) -> Callable:
        _REGISTRY.append((compiled, fn))
        return fn

    return deco


def _lookup(text: str) -> tuple[Callable, dict[str, str]]:
    matches = []
    for pattern, fn in _REGISTRY:
        m = pattern.match(text)
        if m is not None:
            matches.append((fn, m.groupdict()))
    if not matches:
        raise AssertionError(f"unsupported step (no handler matches): {text!r}")
    if len(matches) > 1:
        names = ", ".join(fn.__name__ for fn, _ in matches)
        raise AssertionError(f"ambiguous step (handlers: {names}): {text!r}")
    return matches[0]


# ----------------------------------------------------------- scenario run


def new_world() -> World:
    return World()


def run_scenario(
    world: World,
    spec_path: str,
    scenario_name: str,
    steps: list[tuple[str, str]],
) -> None:
    """Execute ``steps`` (``(keyword, text)`` pairs) against ``world``.

    On any failure the raised AssertionError names the source spec file and
    the failing scenario + step, per the ATDD traceability rule.
    """
    for keyword, text in steps:
        if keyword == "__FAIL__":
            raise AssertionError(
                f"[{spec_path}] scenario {scenario_name!r}: {text}"
            )
        fn, params = _lookup(text)
        try:
            fn(world, **params)
        except AssertionError as exc:
            raise AssertionError(
                f"[{spec_path}] scenario {scenario_name!r} failed at step "
                f"'{keyword} {text}': {exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001 — surfaced with traceability
            raise AssertionError(
                f"[{spec_path}] scenario {scenario_name!r} errored at step "
                f"'{keyword} {text}': {type(exc).__name__}: {exc}"
            ) from exc


# Import feature handler modules so their @step registrations run.
from . import fx_read_time  # noqa: E402,F401
from . import transactions_crud  # noqa: E402,F401
