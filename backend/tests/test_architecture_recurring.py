"""Architecture fitness for the recurring engine (ADR-0035..0038).

The engine's shape rests on two invariants that no unit test would notice
breaking. They are cheap to check and expensive to lose.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "quaestor"
WRITER = SRC / "services" / "occurrences.py"


def _python_files():
    return [p for p in SRC.rglob("*.py") if "migrations" not in p.parts]


def _writes_occurrences(path: Path) -> bool:
    """Constructing a RecurringOccurrence, or assigning an OccurrenceStatus.

    Deliberately keyed on the types, not on what the variable happens to be
    called: a guard that only catches `occ.status = ...` is evaded by renaming
    the variable to `o`, which is worse than no guard because it reads as one.
    """
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and ast.unparse(node.func).endswith("RecurringOccurrence"):
            return True
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        touches_status = any(isinstance(t, ast.Attribute) and t.attr == "status" for t in targets)
        if touches_status and node.value is not None and "OccurrenceStatus" in ast.unparse(node.value):
            return True
    return False


def test_only_one_module_writes_a_recurring_occurrence():
    """Everything that consumes a due date goes through `occurrences.py`.

    Feature 006 used to reach in from `planned.py`; that is what made the rule
    worth stating. If a second module starts writing occurrences, the reason a
    date is settled stops being findable in one place.
    """
    writers = [
        p.relative_to(SRC).as_posix()
        for p in _python_files()
        if p != WRITER and p.name != "models.py" and _writes_occurrences(p)
    ]
    assert writers == [], f"these modules write a RecurringOccurrence but only services/occurrences.py may: {writers}"


def test_the_recurrence_engine_stays_pure():
    """`domain/recurrence.py` is date arithmetic: no session, no services.

    It is the module mutation testing leans on hardest, and that only works
    while it can be exercised without a database.
    """
    tree = ast.parse((SRC / "domain" / "recurrence.py").read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)

    forbidden = {m for m in imported if "service" in m or "sqlmodel" in m or m == "db"}
    assert forbidden == set(), f"domain/recurrence.py must stay pure but imports: {sorted(forbidden)}"


def test_the_transaction_service_never_learns_about_recurring_items():
    """The delete seam is a hook registry, not an import (ADR-0038).

    `transactions.py` belongs to feature 002. It fires whatever is registered
    and stays unaware that a recurring engine exists.
    """
    tree = ast.parse((SRC / "services" / "transactions.py").read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)

    assert not any("occurrence" in m or "recurring" in m for m in imported), (
        f"services/transactions.py imports the recurring engine: {sorted(imported)}"
    )
