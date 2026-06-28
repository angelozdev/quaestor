"""Sort policy: immutable spec + per-service column registry.

`SortSpec` is the value object that callers build and pass to services that
accept `sort` / `order` kwargs. The service resolves the spec against its
own `SortableColumns` registry to produce a SQLAlchemy `(primary, tiebreaker)`
tuple suitable for `.order_by(*spec.resolve(...))`.

Pattern: Value Object + Registry / Lookup table.
SOLID: SRP (the spec only knows about ordering, not filters); OCP (adding a
new sortable field is one line in the service's registry, zero changes here);
DIP (`resolve` accepts the column map and tiebreaker, so the spec has no
direct dependency on a specific SQLModel class).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import ColumnElement

from .errors import ValidationError

# Public API surface — exposed to REST/MCP for input validation.
SortField = Literal["date", "created_at"]
Order = Literal["asc", "desc"]

# Per-service mapping of `sort` value -> SQLAlchemy column attribute.
SortableColumns = dict[str, ColumnElement]


@dataclass(frozen=True, slots=True)
class SortSpec:
    """Immutable (field, order) pair. Resolves to a (primary, tiebreaker)
    tuple suitable for SQLAlchemy `.order_by(*spec.resolve(...))`.

    Frozen + slots: hashable, can't drift between construction and use.
    """

    field: SortField
    order: Order

    def resolve(
        self,
        sortable: SortableColumns,
        tiebreaker: ColumnElement,
    ) -> tuple[ColumnElement, ColumnElement]:
        """Translate (field, order) into a (primary, tiebreaker) tuple.

        Both expressions share the same direction (so that the tiebreaker
        is consistent when two rows share the primary value).

        Raises:
            ValidationError: `field` is not in `sortable`. The Literal type
                prevents this at type-check time, but a caller that bypasses
                the type system (e.g. dict-construction) will hit this.
        """
        col = sortable.get(self.field)
        if col is None:
            raise ValidationError(
                f"unknown sort field: {self.field!r}; "
                f"allowed: {sorted(sortable)}"
            )
        desc = self.order == "desc"
        return (
            col.desc() if desc else col.asc(),
            tiebreaker.desc() if desc else tiebreaker.asc(),
        )