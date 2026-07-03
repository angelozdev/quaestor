"""Outstanding-queue value object for the planned-payments domain.

The VO is a pure-data container: two lists (`overdue`, `upcoming`) and
two derived properties (`total_base`, `is_empty`). It depends only on
`Transaction` and stdlib; no DB, no session, no I/O. The construction
site (`services.planned.to_pay`) is the only place that produces an
`OutstandingQueue`, and the date ranges it queries are disjoint by
construction — so the mutual-exclusion invariant between buckets is
preserved at the call site, not enforced at the VO.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .models import Transaction


@dataclass(frozen=True, slots=True)
class OutstandingQueue:
    """The user's outstanding obligations: past-due + upcoming.

    `overdue` and `upcoming` are mutually exclusive by construction
    (the date ranges that produce them don't overlap). The two lists
    together cover "what the user owes or is about to owe" through the
    caller-supplied `until`. `total_base` is the COP-cents sum of both
    buckets, computed at access time.
    """

    overdue: list[Transaction] = field(default_factory=list)
    upcoming: list[Transaction] = field(default_factory=list)

    @property
    def total_base(self) -> int:
        """Sum of `to_base` (COP cents) across both buckets."""
        return sum(t.to_base for t in self.overdue) + sum(
            t.to_base for t in self.upcoming
        )

    @property
    def is_empty(self) -> bool:
        return not self.overdue and not self.upcoming

    def all_items(self) -> list[Transaction]:
        """Flat list, overdue first then upcoming. Cheap (returns a fresh list)."""
        return [*self.overdue, *self.upcoming]

    @classmethod
    def from_lists(
        cls, overdue: Iterable[Transaction], upcoming: Iterable[Transaction]
    ) -> "OutstandingQueue":
        """Construct with eager evaluation; both iterables are consumed once."""
        return cls(overdue=list(overdue), upcoming=list(upcoming))
