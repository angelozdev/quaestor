"""Outstanding-queue value object for the planned-payments domain.

The VO is a pure-data container: two lists (`overdue`, `upcoming`), an
`is_empty` property, and a read-time COP total that takes the caller's
TRM. It depends only on `Transaction` and stdlib; no DB, no session, no
I/O. The construction site (`services.planned.to_pay`) is the only place
that produces an `OutstandingQueue`, and the date ranges it queries are
disjoint by construction — so the mutual-exclusion invariant between
buckets is preserved at the call site, not enforced at the VO.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from .models import Transaction
from .money import to_cop_cents


@dataclass(frozen=True, slots=True)
class OutstandingQueue:
    """The user's outstanding obligations: past-due + upcoming.

    `overdue` and `upcoming` are mutually exclusive by construction
    (the date ranges that produce them don't overlap). The two lists
    together cover "what the user owes or is about to owe" through the
    caller-supplied `until`. `total_cop_cents(trm)` is the read-time COP
    sum of both buckets at the caller's TRM (ADR-0031).
    """

    overdue: list[Transaction] = field(default_factory=list)
    upcoming: list[Transaction] = field(default_factory=list)

    def total_cop_cents(self, trm: Decimal) -> int:
        """COP cents across both buckets, converted at `trm`."""
        return sum(
            to_cop_cents(t.amount, t.currency, trm) for t in self.all_items()
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
    ) -> OutstandingQueue:
        """Construct with eager evaluation; both iterables are consumed once."""
        return cls(overdue=list(overdue), upcoming=list(upcoming))
