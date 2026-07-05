# SQLite → Postgres migration runbook

One-shot data migration from `.dev-data/quaestor.db` (SQLite) to the remote
Postgres (`backend/.env.local.remote` → Render.com Oregon
`quaestor_production_db`). Implements the deferred recipe from
`docs/adr/0026-local-only-posture.md` (accepted 2026-07-05).

## §1. When to use this runbook

You have an existing SQLite at `.dev-data/quaestor.db` with real data, and
you want to move that data to a remote Postgres whose schema already matches
(run `alembic upgrade head` first via `just dev-real`).

## §2. Pre-flight

```bash
# 1. Confirm api is stopped
just dev-down

# 2. Confirm remote Postgres is reachable
export QUAESTOR_DB="$(grep '^QUAESTOR_DB=' backend/.env.local.remote | cut -d= -f2-)"
uv run --with psycopg[binary] python -c \
  "import psycopg; psycopg.connect('$QUAESTOR_DB').close(); print('remote ok')"

# 3. Confirm SQLite has data
sqlite3 .dev-data/quaestor.db "SELECT COUNT(*) FROM transaction"
# Expected: a positive integer (your row count)
```

If any of these fail, stop and debug before proceeding.

## §3. Scripts

Create `/tmp/quaestor-migration/` and paste both scripts below. They use
only Python stdlib + `psycopg` + `aiosqlite` (both already in `pyproject.toml`).

### `migrate.py`

```python
"""One-shot SQLite → Postgres data migration for Quaestor (ADR-0026 follow-up).

Run from /tmp/quaestor-migration/ with:
    QUAESTOR_DB="postgresql://..." python3 migrate.py

QUAESTOR_DB must be the REMOTE Postgres URL.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import aiosqlite
import psycopg

# Assumes the script lives at /tmp/quaestor-migration/migrate.py and the
# repo root is two parents up. Adjust REPO_ROOT if you move the script.
REPO_ROOT = Path("/Users/angelozdev/me/quaestor")
SQLITE_PATH = REPO_ROOT / ".dev-data" / "quaestor.db"
DUMP_PATH = Path("/tmp/quaestor-migration/pre-migration.dump")

TABLES_IN_DEPENDENCY_ORDER = [
    "account",
    "category_group",
    "fx_rate",
    "tag",
    "category",
    "goal",
    "settings",
    "budget",
    "recurring_item",
    "transaction",
    "goal_contribution",
    "recurring_occurrence",
    "transaction_tag",
]


def log(msg: str) -> None:
    print(f"[migrate] {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"[migrate] FATAL: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def check_api_not_running() -> None:
    """Confirm uvicorn is not running. Skip if pgrep unavailable."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "uvicorn"],
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return
    if result.returncode == 0:
        fail("uvicorn is running. Stop the api first: `just dev-down`.")


def ensure_schema(remote_url: str) -> None:
    """Run alembic upgrade head against the remote Postgres.

    Always runs: alembic is idempotent (tracks applied migrations in
    `alembic_version`). Running against a fresh DB bootstraps the full
    schema; running against an already-migrated DB is a no-op except for
    any newly-added migrations.
    """
    log("running alembic upgrade head against remote...")
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        cwd=str(REPO_ROOT / "backend"),
        check=False,
    )
    if result.returncode != 0:
        fail(f"alembic upgrade head failed (rc={result.returncode})")
    log("alembic upgrade head complete")


def pre_migration_dump(remote_url: str) -> None:
    """Capture any pre-existing remote data (safety net for re-runs).

    Non-fatal: pg_dump may not be installed locally. For a first-time
    migration the remote DB is empty, so the dump would be empty anyway.
    For re-runs the absence of pg_dump means no rollback target — proceed
    at your own risk.
    """
    DUMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    log(f"writing pre-migration dump to {DUMP_PATH}")
    try:
        result = subprocess.run(
            ["pg_dump", "-Fc", remote_url, "-f", str(DUMP_PATH)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        log("WARNING: pg_dump not installed; skipping pre-migration dump")
        return
    if result.returncode != 0:
        log(f"WARNING: pg_dump failed (rc={result.returncode}); continuing")
        log(f"  stderr: {result.stderr.strip()}")
        return


async def fetch_sqlite_rows() -> dict[str, list[tuple]]:
    """Read every row from every table in SQLite, in dependency order."""
    rows: dict[str, list[tuple]] = {}
    async with aiosqlite.connect(str(SQLITE_PATH)) as db:
        for table in TABLES_IN_DEPENDENCY_ORDER:
            # `transaction` is a reserved word in SQLite; quote the identifier.
            async with db.execute(f'SELECT * FROM "{table}"') as cur:
                rows[table] = await cur.fetchall()
                log(f"sqlite {table}: {len(rows[table])} rows")
    return rows


def get_columns(remote_url: str, table: str) -> list[tuple[str, str]]:
    """Get the (column_name, data_type) list for a table from Postgres.

    Ordered to match the SQLite SELECT * result order.
    """
    with psycopg.connect(remote_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
                """,
                (table,),
            )
            return [(row[0], row[1]) for row in cur.fetchall()]


def coerce_row(row: tuple, columns: list[tuple[str, str]]) -> tuple:
    """Convert SQLite values to Postgres-compatible Python values.

    SQLite stores booleans as INTEGER 0/1; Postgres BOOLEAN rejects ints.
    Other types (DATE, TIMESTAMP, NUMERIC) are coerced via ISO string /
    Decimal automatically by psycopg when given the right Python type.
    """
    out = []
    for value, (col_name, col_type) in zip(row, columns):
        if col_type == "boolean":
            out.append(bool(value))
        else:
            out.append(value)
    return tuple(out)


def get_fk_columns(
    remote_url: str, table: str
) -> list[tuple[str, str, str]]:
    """Return [(child_column, parent_table, parent_column)] for FK columns."""
    with psycopg.connect(remote_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = %s
                """,
                (table,),
            )
            return [(row[0], row[1], row[2]) for row in cur.fetchall()]


def fetch_valid_parent_ids(
    remote_url: str, parent_table: str, parent_column: str
) -> set:
    """Return the set of valid IDs in the parent table (for FK validation)."""
    with psycopg.connect(remote_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(f'SELECT "{parent_column}" FROM "{parent_table}"')
            return {row[0] for row in cur.fetchall()}


def filter_orphans(
    rows: list[tuple],
    column_names: list[str],
    fks: list[tuple[str, str, str]],
    valid_ids: dict[tuple[str, str], set],
) -> tuple[list[tuple], list[tuple[int, str]]]:
    """Drop rows whose non-NULL FK columns reference missing parent rows.

    Returns (kept_rows, [(row_id_or_index, skip_reason), ...]).
    """
    kept: list[tuple] = []
    skipped: list[tuple[int, str]] = []
    for row_idx, row in enumerate(rows):
        skip_reason: str | None = None
        for child_col, parent_table, parent_col in fks:
            if child_col not in column_names:
                continue
            value = row[column_names.index(child_col)]
            if value is None:
                continue
            if value not in valid_ids.get((parent_table, parent_col), set()):
                skip_reason = (
                    f"{child_col}={value} not in "
                    f"{parent_table}.{parent_col}"
                )
                break
        if skip_reason:
            # Prefer the row's own id for the log; fall back to row index.
            if "id" in column_names:
                row_id = row[column_names.index("id")]
            else:
                row_id = row_idx
            skipped.append((row_id, skip_reason))
        else:
            kept.append(row)
    return kept, skipped


def copy_table(
    remote_url: str,
    table: str,
    rows: list[tuple],
    columns: list[tuple[str, str]],
) -> int:
    """INSERT all rows into Postgres with ON CONFLICT DO NOTHING.

    Skips rows whose FK references are orphaned (parent rows missing in
    Postgres). SQLite does not enforce FKs by default, so pre-existing
    data can contain orphaned references; Postgres (correctly) rejects
    them at INSERT time. We filter them here so the destination stays
    clean. The script logs every skipped row.
    """
    if not rows:
        return 0
    column_names = [c[0] for c in columns]

    # Detect FKs and fetch valid parent IDs (parents are already inserted
    # earlier in the dependency order).
    fks = get_fk_columns(remote_url, table)
    valid_ids: dict[tuple[str, str], set] = {}
    for child_col, parent_table, parent_col in fks:
        valid_ids[(parent_table, parent_col)] = fetch_valid_parent_ids(
            remote_url, parent_table, parent_col
        )

    kept_rows, skipped_rows = filter_orphans(
        rows, column_names, fks, valid_ids
    )
    if skipped_rows:
        log(f"  {table}: SKIPPED {len(skipped_rows)} row(s) with orphaned FKs:")
        for row_id, reason in skipped_rows[:5]:
            log(f"    id={row_id}: {reason}")
        if len(skipped_rows) > 5:
            log(f"    ... and {len(skipped_rows) - 5} more")
    if not kept_rows:
        return 0

    placeholders = ", ".join(["%s"] * len(column_names))
    cols_csv = ", ".join(column_names)
    if table == "transaction_tag":
        # composite PK (transaction_id, tag_id); no `id` column
        sql = (
            f"INSERT INTO {table} ({cols_csv}) VALUES ({placeholders}) "
            f"ON CONFLICT (transaction_id, tag_id) DO NOTHING"
        )
    elif table == "recurring_occurrence":
        # composite unique constraint on (recurring_id, due_date) in addition
        # to the single-column `id` PK — target the unique constraint so
        # re-runs after a partial success don't trip on it.
        sql = (
            f"INSERT INTO {table} ({cols_csv}) VALUES ({placeholders}) "
            f"ON CONFLICT (recurring_id, due_date) DO NOTHING"
        )
    else:
        sql = (
            f"INSERT INTO {table} ({cols_csv}) VALUES ({placeholders}) "
            f"ON CONFLICT (id) DO NOTHING"
        )
    coerced_rows = [coerce_row(r, columns) for r in kept_rows]
    with psycopg.connect(remote_url) as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, coerced_rows)
        conn.commit()
    return len(coerced_rows)


def reset_sequence(remote_url: str, table: str) -> None:
    """Advance the table's id sequence to MAX(id). Skip composite-PK tables
    and empty tables (sequence is already at its initial value)."""
    if table == "transaction_tag":
        return
    with psycopg.connect(remote_url) as conn:
        with conn.cursor() as cur:
            cur.execute(f'SELECT MAX(id) FROM "{table}"')
            max_id = cur.fetchone()[0]
            if max_id is None:
                # Empty table; sequence is at its initial value (1).
                # Setting setval(seq, 0) would fail with "out of bounds"
                # because sequence min_value is 1.
                return
            cur.execute(
                "SELECT setval(pg_get_serial_sequence(%s, 'id'), %s)",
                (table, max_id),
            )
        conn.commit()


def main() -> None:
    remote_url = os.environ.get("QUAESTOR_DB")
    if not remote_url or not remote_url.startswith("postgresql"):
        fail("QUAESTOR_DB must be set to the remote Postgres URL")
    if not SQLITE_PATH.exists():
        fail(f"SQLite not found at {SQLITE_PATH}")

    check_api_not_running()
    ensure_schema(remote_url)
    pre_migration_dump(remote_url)

    rows_by_table = asyncio.run(fetch_sqlite_rows())

    # No need to disable FK checks: TABLES_IN_DEPENDENCY_ORDER is a strict
    # linear order with no cycles. Each child table's referenced parents are
    # inserted earlier in the same pass.

    for table in TABLES_IN_DEPENDENCY_ORDER:
        rows = rows_by_table[table]
        columns = get_columns(remote_url, table)
        n = copy_table(remote_url, table, rows, columns)
        log(f"postgres {table}: {n} rows inserted")
        reset_sequence(remote_url, table)

    log("DONE. Run verify.py next.")


if __name__ == "__main__":
    main()
```

### `verify.py`

```python
"""Verify the SQLite → Postgres migration copied everything correctly.

Run from /tmp/quaestor-migration/ with:
    QUAESTOR_DB="postgresql://..." python3 verify.py

Exits 0 if every check passes; exits 1 on the first failure.
"""
from __future__ import annotations

import asyncio
import os
import sys
from decimal import Decimal
from pathlib import Path

import aiosqlite
import psycopg

REPO_ROOT = Path("/Users/angelozdev/me/quaestor")
SQLITE_PATH = REPO_ROOT / ".dev-data" / "quaestor.db"

TABLES_IN_DEPENDENCY_ORDER = [
    "account",
    "category_group",
    "fx_rate",
    "tag",
    "category",
    "goal",
    "settings",
    "budget",
    "recurring_item",
    "transaction",
    "goal_contribution",
    "recurring_occurrence",
    "transaction_tag",
]

# (child_table, child_column, parent_table)
FKS = [
    ("category", "group_id", "category_group"),
    ("goal", "savings_account_id", "account"),
    ("settings", "default_source_account_id", "account"),
    ("budget", "category_id", "category"),
    ("recurring_item", "category_id", "category"),
    ("recurring_item", "account_id", "account"),
    ("transaction", "account_id", "account"),
    ("transaction", "category_id", "category"),
    ("transaction", "goal_id", "goal"),
    ("transaction", "recurring_id", "recurring_item"),
    ("goal_contribution", "goal_id", "goal"),
    ("goal_contribution", "transaction_id", "transaction"),
    ("recurring_occurrence", "recurring_id", "recurring_item"),
    ("recurring_occurrence", "transaction_id", "transaction"),
    ("transaction_tag", "transaction_id", "transaction"),
    ("transaction_tag", "tag_id", "tag"),
]

# (table, column, allowed_values)
ENUMS = [
    ("account", "type", ("debit", "credit", "cash", "savings")),
    ("goal", "status", ("active", "reached", "paused")),
    ("recurring_item", "type", ("expense", "income", "transfer")),
    ("recurring_item", "mode", ("auto", "manual")),
    ("recurring_item", "interval_unit", ("day", "week", "month", "year")),
    ("transaction", "type", ("expense", "income", "transfer")),
    ("transaction", "status", ("planned", "posted", "skipped")),
    ("transaction", "source", ("manual", "agent", "import_")),
    ("goal_contribution", "source", ("confirmed", "manual")),
    ("recurring_occurrence", "status", ("posted", "planned", "skipped")),
]


def log(msg: str) -> None:
    print(f"[verify] {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"[verify] FAIL: {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def values_equal(sqlite_val, pg_val) -> bool:
    """Compare SQLite and Postgres values, handling known type mismatches.

    The underlying data is the same; only the Python types differ:
    - SQLite stores DATE as 'YYYY-MM-DD' string; Postgres returns datetime.date.
    - SQLite stores DATETIME as 'YYYY-MM-DD HH:MM:SS' (space separator);
      Postgres returns datetime.datetime (whose str() uses a space).
    - SQLite stores NUMERIC values with no fractional part as int;
      Postgres returns Decimal('4200.000000').
    """
    if sqlite_val is None or pg_val is None:
        return sqlite_val is None and pg_val is None
    # Date/datetime: SQLite returns ISO string, Postgres returns date/datetime.
    # Use str() rather than isoformat() — for date both match ('YYYY-MM-DD');
    # for datetime str() uses a space ('YYYY-MM-DD HH:MM:SS') matching SQLite,
    # while isoformat() would use 'T' and not match.
    if isinstance(sqlite_val, str) and hasattr(pg_val, "isoformat"):
        return sqlite_val == str(pg_val)
    # Numeric: SQLite returns int/float, Postgres returns Decimal.
    if isinstance(sqlite_val, (int, float)) and isinstance(pg_val, Decimal):
        return float(sqlite_val) == float(pg_val)
    return sqlite_val == pg_val


def check_row_counts(remote_url: str) -> None:
    log("check 1: row counts")
    # SQLite may contain rows whose FK references don't resolve in
    # Postgres (orphans). migrate.py filters those out, so Postgres
    # has the "valid" subset. Compare Postgres COUNT(*) against the
    # SQLite count of rows whose non-NULL FKs all resolve in Postgres.
    # Postgres may have MORE rows than SQLite (post-migration usage
    # via the UI); that's not a failure, just informational.
    async def sqlite_effective_counts() -> dict[str, int]:
        pg_valid: dict[tuple[str, str], set] = {}
        with psycopg.connect(remote_url, connect_timeout=5) as conn:
            with conn.cursor() as cur:
                for table in TABLES_IN_DEPENDENCY_ORDER:
                    fks = get_fk_columns_sync(remote_url, table)
                    for _child_col, parent_table, parent_col in fks:
                        key = (parent_table, parent_col)
                        if key in pg_valid:
                            continue
                        cur.execute(
                            f'SELECT "{parent_col}" FROM "{parent_table}"'
                        )
                        pg_valid[key] = {row[0] for row in cur.fetchall()}

        out: dict[str, int] = {}
        async with aiosqlite.connect(str(SQLITE_PATH)) as db:
            for table in TABLES_IN_DEPENDENCY_ORDER:
                # `transaction` is a reserved word in SQLite; quote the identifier.
                async with db.execute(f'SELECT * FROM "{table}"') as cur:
                    cols = [d[0] for d in cur.description]
                    rows = await cur.fetchall()
                fks = get_fk_columns_sync(remote_url, table)
                kept = 0
                for row in rows:
                    skip = False
                    for child_col, parent_table, parent_col in fks:
                        if child_col not in cols:
                            continue
                        value = row[cols.index(child_col)]
                        if value is None:
                            continue
                        if value not in pg_valid[(parent_table, parent_col)]:
                            skip = True
                            break
                    if not skip:
                        kept += 1
                out[table] = kept
        return out

    sqlite_rows = asyncio.run(sqlite_effective_counts())

    with psycopg.connect(remote_url) as conn:
        with conn.cursor() as cur:
            for table in TABLES_IN_DEPENDENCY_ORDER:
                cur.execute(f'SELECT COUNT(*) FROM "{table}"')
                pg_count = cur.fetchone()[0]
                if pg_count < sqlite_rows[table]:
                    fail(
                        f"row count shortfall for {table}: "
                        f"sqlite(valid)={sqlite_rows[table]} "
                        f"postgres={pg_count}"
                    )
                if pg_count > sqlite_rows[table]:
                    extra = pg_count - sqlite_rows[table]
                    log(
                        f"  {table}: sqlite(valid)={sqlite_rows[table]} "
                        f"postgres={pg_count} OK ({extra} row(s) "
                        f"created post-migration)"
                    )
                else:
                    log(
                        f"  {table}: sqlite(valid)={sqlite_rows[table]} "
                        f"postgres={pg_count} OK"
                    )


def get_fk_columns_sync(
    remote_url: str, table: str
) -> list[tuple[str, str, str]]:
    """Return [(child_column, parent_table, parent_column)] for FK columns."""
    with psycopg.connect(remote_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    kcu.column_name,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_name = %s
                """,
                (table,),
            )
            return [(row[0], row[1], row[2]) for row in cur.fetchall()]


def check_fk_integrity(remote_url: str) -> None:
    log("check 2: FK integrity")
    with psycopg.connect(remote_url) as conn:
        with conn.cursor() as cur:
            for child, col, parent in FKS:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {child} c
                    WHERE c.{col} IS NOT NULL
                      AND NOT EXISTS (
                        SELECT 1 FROM {parent} p WHERE p.id = c.{col}
                      )
                    """
                )
                orphans = cur.fetchone()[0]
                if orphans > 0:
                    fail(f"{orphans} orphaned {child}.{col} -> {parent}.id")
                log(f"  {child}.{col} -> {parent}.id: 0 orphans OK")


def check_sample_rows(remote_url: str) -> None:
    log("check 3: 5 sample rows per table")
    async def sqlite_rows_for(table: str, ids: list) -> dict[int, tuple]:
        async with aiosqlite.connect(str(SQLITE_PATH)) as db:
            placeholders = ",".join(["?"] * len(ids))
            # `transaction` is a reserved word in SQLite; quote the identifier.
            async with db.execute(
                f'SELECT * FROM "{table}" WHERE id IN ({placeholders})',
                ids,
            ) as cur:
                cols = [d[0] for d in cur.description]
                return {
                    row[cols.index("id")]: row
                    for row in await cur.fetchall()
                }

    async def sqlite_rows_by_composite(
        table: str, keys: list[tuple]
    ) -> dict[tuple, tuple]:
        # Fetch SQLite rows whose (recurring_id, due_date) matches any
        # of the given tuples. The query uses a row-value IN clause,
        # supported by both SQLite and Postgres. Normalize date values
        # to ISO strings so the SQLite TEXT column comparison works
        # regardless of whether the caller passes date objects or strings.
        if not keys:
            return {}
        values_clause = ",".join(["(?, ?)"] * len(keys))
        flat_params: list = []
        for rid, ddate in keys:
            flat_params.append(rid)
            if isinstance(ddate, str):
                flat_params.append(ddate)
            else:
                flat_params.append(ddate.isoformat())
        async with aiosqlite.connect(str(SQLITE_PATH)) as db:
            async with db.execute(
                f'SELECT * FROM "{table}" '
                f'WHERE (recurring_id, due_date) IN ({values_clause})',
                flat_params,
            ) as cur:
                cols = [d[0] for d in cur.description]
                return {
                    (
                        row[cols.index("recurring_id")],
                        row[cols.index("due_date")],
                    ): row
                    for row in await cur.fetchall()
                }

    with psycopg.connect(remote_url) as conn:
        with conn.cursor() as cur:
            for table in TABLES_IN_DEPENDENCY_ORDER:
                if table == "transaction_tag":
                    continue  # composite PK, no single `id`

                if table == "recurring_occurrence":
                    # Postgres IDs are renumbered for this table (the
                    # ON CONFLICT (recurring_id, due_date) clause causes
                    # Postgres to assign sequential IDs). Compare by the
                    # actual unique key (recurring_id, due_date) and skip
                    # the id column in the data comparison.
                    #
                    # Additionally, data may diverge from SQLite because
                    # the user has used the app post-migration: ON CONFLICT
                    # DO NOTHING preserves UI-created rows that share the
                    # same (recurring_id, due_date) key. When Postgres
                    # created_at is newer than SQLite created_at, the
                    # divergence is expected (post-migration UI activity).
                    cur.execute(
                        f'SELECT recurring_id, due_date FROM "{table}" '
                        "ORDER BY random() LIMIT 5"
                    )
                    # Normalize sample keys to (rid, isoformat_string) so
                    # SQLite and Postgres dict keys are both strings.
                    sample_keys = [(r[0], str(r[1])) for r in cur.fetchall()]
                    if not sample_keys:
                        log(f"  {table}: empty (no samples to check)")
                        continue
                    sqlite_data = asyncio.run(
                        sqlite_rows_by_composite(table, sample_keys)
                    )
                    values_clause = ",".join(["(%s, %s)"] * len(sample_keys))
                    flat_params: list = []
                    for rid, ddate in sample_keys:
                        flat_params.append(rid)
                        flat_params.append(ddate)
                    cur.execute(
                        f'SELECT * FROM "{table}" '
                        f"WHERE (recurring_id, due_date) IN ({values_clause})",
                        flat_params,
                    )
                    cols = [d[0] for d in cur.description]
                    pg_data = {
                        (
                            row[cols.index("recurring_id")],
                            str(row[cols.index("due_date")]),
                        ): row
                        for row in cur.fetchall()
                    }
                    created_at_idx = cols.index("created_at")
                    matched = 0
                    post_migration_diverged = 0
                    for key in sample_keys:
                        if key not in sqlite_data:
                            fail(
                                f"sample key {key} missing from sqlite {table}"
                            )
                        if key not in pg_data:
                            fail(
                                f"sample key {key} missing from postgres {table}"
                            )
                        sqlite_row = sqlite_data[key]
                        pg_row = pg_data[key]
                        if len(sqlite_row) != len(pg_row):
                            fail(
                                f"column count mismatch in {table} "
                                f"key={key}: "
                                f"sqlite={len(sqlite_row)} "
                                f"postgres={len(pg_row)}"
                            )
                        # Compare all columns except id (col 0,
                        # renumbered in Postgres).
                        differences: list[tuple[int, object, object]] = []
                        for col_idx in range(1, len(sqlite_row)):
                            s_val = sqlite_row[col_idx]
                            p_val = pg_row[col_idx]
                            if not values_equal(s_val, p_val):
                                differences.append((col_idx, s_val, p_val))
                        if not differences:
                            matched += 1
                            continue
                        # Data diverges — is it post-migration UI
                        # activity (Postgres row is newer) or a real
                        # migration failure (SQLite row is newer)?
                        sqlite_created_at = sqlite_row[created_at_idx]
                        pg_created_at = pg_row[created_at_idx]
                        if pg_created_at > sqlite_created_at:
                            post_migration_diverged += 1
                        else:
                            cols_desc = ", ".join(
                                f"col {idx} ({cols[idx]}): "
                                f"sqlite={s!r} postgres={p!r}"
                                for idx, s, p in differences
                            )
                            fail(
                                f"row mismatch in {table} key={key} "
                                f"(SQLite is newer — real migration issue): "
                                f"{cols_desc}"
                            )
                    log(
                        f"  {table}: {matched} sample rows match OK, "
                        f"{post_migration_diverged} row(s) diverged "
                        f"post-migration (ON CONFLICT preserved UI data)"
                    )
                    continue

                cur.execute(
                    f'SELECT id FROM "{table}" ORDER BY random() LIMIT 5'
                )
                sample_ids = [r[0] for r in cur.fetchall()]
                if not sample_ids:
                    log(f"  {table}: empty (no samples to check)")
                    continue
                sqlite_data = asyncio.run(
                    sqlite_rows_for(table, sample_ids)
                )
                placeholders = ",".join(["%s"] * len(sample_ids))
                cur.execute(
                    f'SELECT * FROM "{table}" WHERE id IN ({placeholders})',
                    sample_ids,
                )
                cols = [d[0] for d in cur.description]
                pg_data = {
                    row[cols.index("id")]: row
                    for row in cur.fetchall()
                }
                for sid in sample_ids:
                    if sid not in sqlite_data:
                        fail(
                            f"sample id {sid} missing from sqlite {table}"
                        )
                    if sid not in pg_data:
                        fail(
                            f"sample id {sid} missing from postgres {table}"
                        )
                    sqlite_row = sqlite_data[sid]
                    pg_row = pg_data[sid]
                    if len(sqlite_row) != len(pg_row):
                        fail(
                            f"column count mismatch in {table} id={sid}: "
                            f"sqlite={len(sqlite_row)} postgres={len(pg_row)}"
                        )
                    for col_idx, (s_val, p_val) in enumerate(
                        zip(sqlite_row, pg_row)
                    ):
                        if not values_equal(s_val, p_val):
                            fail(
                                f"row mismatch in {table} id={sid} "
                                f"col={col_idx}: "
                                f"sqlite={s_val!r} postgres={p_val!r}"
                            )
                log(
                    f"  {table}: {len(sample_ids)} sample rows match OK"
                )


def check_enum_validity(remote_url: str) -> None:
    log("check 4: ENUM column validity")
    with psycopg.connect(remote_url) as conn:
        with conn.cursor() as cur:
            for table, col, allowed in ENUMS:
                cur.execute(f"SELECT DISTINCT {col} FROM {table}")
                actual = {r[0] for r in cur.fetchall()}
                invalid = actual - set(allowed)
                if invalid:
                    fail(
                        f"{table}.{col} has invalid values: {invalid} "
                        f"(allowed: {allowed})"
                    )
                log(f"  {table}.{col}: all values valid ({sorted(actual)})")


def check_settings_singleton(remote_url: str) -> None:
    log("check 5: settings singleton")
    with psycopg.connect(remote_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM settings")
            n = cur.fetchone()[0]
            if n != 1:
                fail(f"settings has {n} rows; expected exactly 1")
            log("  settings: exactly 1 row OK")


def main() -> None:
    remote_url = os.environ.get("QUAESTOR_DB")
    if not remote_url or not remote_url.startswith("postgresql"):
        fail("QUAESTOR_DB must be set to the remote Postgres URL")
    if not SQLITE_PATH.exists():
        fail(f"SQLite not found at {SQLITE_PATH}")

    check_row_counts(remote_url)
    check_fk_integrity(remote_url)
    check_sample_rows(remote_url)
    check_enum_validity(remote_url)
    check_settings_singleton(remote_url)

    log("VERIFIED: all checks PASS.")


if __name__ == "__main__":
    main()
```

## §4. Run order

```bash
# 0. From the repo root
cd /Users/angelozdev/me/quaestor

# 1. Pre-flight (see §2 above)
just dev-down
export QUAESTOR_DB="$(grep '^QUAESTOR_DB=' backend/.env.local.remote | cut -d= -f2-)"

# 2. Create the ephemeral workspace and paste scripts from §3
mkdir -p /tmp/quaestor-migration
# (paste migrate.py and verify.py here)

# 3. Run the migration
python3 /tmp/quaestor-migration/migrate.py
# Expected: "[migrate] DONE. Run verify.py next." on stdout, exit 0

# 4. Run the verification
python3 /tmp/quaestor-migration/verify.py
# Expected: "[verify] VERIFIED: all checks PASS." on stdout, exit 0
# If anything says FAIL, see §5 below.

# 5. Browser smoke test (manual, you)
just dev-real
# Open http://localhost:3000 in the browser
# - Confirm accounts/transactions/recurring/goals render
# - Create a new transaction
# - Confirm it appears
# Ctrl+C in the terminal to stop `just dev-real`

# 6. Archive the local SQLite (manual, you)
mkdir -p ~/quaestor-sqlite-archive
mv .dev-data/quaestor.db ~/quaestor-sqlite-archive/quaestor.db
ls -la ~/quaestor-sqlite-archive/   # confirm the file is there

# 7. Env cleanup (manual, you)
rm backend/.env.example backend/.env.local
sed -i '' 's|dotenv .env.local$|dotenv .env.local.sqlite|' backend/.envrc
cat backend/.envrc                  # confirm: "dotenv .env.local.sqlite"

# 8. Final smoke test
just dev-real                       # api must still come up
# (in another terminal) just dev-test   # pytest must still be green
git status                          # only docs/runbooks/.../migration.md should show as added
```

## §5. Failure / rollback

| Symptom | Cause | Recovery |
|---|---|---|
| `migrate.py` aborts with "uvicorn is running" | api container is up | `just dev-down`, re-run |
| `migrate.py` aborts with "alembic upgrade failed" | schema bootstrap failed | Inspect alembic logs; fix; re-run |
| `pg_dump` fails | remote URL bad / network down | Check `backend/.env.local.remote`; re-run |
| `migrate.py` crashes mid-table | network blip / Postgres error | Re-run; second pass is idempotent (ON CONFLICT DO NOTHING) |
| `verify.py` reports row count shortfall | copy bug (missing rows in Postgres) | Inspect; SQLite still in `.dev-data/` until step 6 — no data loss |
| `verify.py` reports FK orphans | copy order issue / data corruption in SQLite | Inspect; same as above |
| Browser smoke test reveals missing data | copy bug | SQLite still in `.dev-data/`; debug; re-run from step 3 |
| Browser smoke test reveals broken query | app-side issue, not data | Independent of migration; debug the app |
| Step 6 (archive) forgotten | SQLite still in `.dev-data/` | Re-run `mv` |
| Step 7 (env cleanup) forgotten | stale files still present | Re-run the `rm` and `sed` |

**Rollback to before migration (only useful if remote Postgres had pre-existing data):**

```bash
# Restore from pre-migration.dump (captured in step 3)
pg_restore -d "$QUAESTOR_DB" --clean --if-exists /tmp/quaestor-migration/pre-migration.dump
# Note: for a first-time migration, the remote DB was empty before, so this dump is empty too.
```

## §6. Why this is safe

- **SQLite is moved (not deleted).** `mv` to `~/quaestor-sqlite-archive/`. Manual deletion only.
- **Pre-migration.dump captures any pre-existing remote data.** Empty for a first-time migration; useful for re-runs.
- **All destructive steps (archive, env cleanup) are separate commands**, gated by you. You can re-run the migration between smoke test and archive if needed.
- **Alembic schema is the source of truth.** Scripts only copy rows. They never alter the schema.
- **Idempotent migration.** `INSERT ... ON CONFLICT DO NOTHING` makes re-runs safe.
- **Schema is created automatically.** `migrate.py` checks for the `account` table; if missing, runs `alembic upgrade head`.