"""Request-scoped dependencies for the API layer."""
from __future__ import annotations

from collections.abc import Generator

from sqlmodel import Session

from ..db import engine


def get_session() -> Generator[Session, None, None]:
    """Yield a Session bound to the process engine, closed when the request ends.

    Tests override this via app.dependency_overrides to bind an in-memory engine.
    """
    with Session(engine) as s:
        yield s
