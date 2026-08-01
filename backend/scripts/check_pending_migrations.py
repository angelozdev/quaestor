"""Refuse to start the stack while Alembic revisions are pending (ADR-0033).

Run inside the api container before `docker compose up`, so a schema change
against real data is announced and backup-gated instead of applied silently.

Exit codes: 0 = at head, or a bootstrap case the entrypoint handles without
altering an existing schema; 1 = revisions pending; 2 = cannot tell.
"""
from __future__ import annotations

import os
import sys
from typing import Final

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

ALEMBIC_INI: Final = os.environ.get("QUAESTOR_ALEMBIC_INI", "/app/alembic.ini")
_POSTGRESQL_SCHEME: Final = "postgresql://"
_PSYCOPG_SCHEME: Final = "postgresql+psycopg://"


def _resolve_db_url(url: str) -> str:
    if url.startswith(_POSTGRESQL_SCHEME):
        return _PSYCOPG_SCHEME + url[len(_POSTGRESQL_SCHEME):]
    return url


def _applied_revisions(url: str) -> set[str]:
    engine = create_engine(_resolve_db_url(url))
    with engine.connect() as conn:
        return set(MigrationContext.configure(conn).get_current_heads())


def _describe(revision) -> str:
    return f"  {revision.revision}  {revision.doc or ''}".rstrip()


def main() -> int:
    url = os.environ.get("QUAESTOR_DB")
    if not url:
        print("QUAESTOR_DB is unset; refusing to guess the target database")
        return 2

    try:
        applied = _applied_revisions(url)
    except Exception as exc:
        print(f"database unreachable, cannot check for pending revisions: {exc}")
        return 2

    script = ScriptDirectory.from_config(Config(ALEMBIC_INI))
    heads = set(script.get_heads())

    if not applied:
        print("no alembic_version row; the entrypoint will stamp or bootstrap")
        return 0

    if applied == heads:
        print(f"database at head ({', '.join(sorted(heads))})")
        return 0

    pending = list(script.iterate_revisions("heads", next(iter(sorted(applied)))))
    print(f"{len(pending)} pending revision(s) against {', '.join(sorted(applied))}:")
    for revision in reversed(pending):
        print(_describe(revision))
    print("")
    print("This database holds real data. Run `just backup`, then `just migrate`.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
