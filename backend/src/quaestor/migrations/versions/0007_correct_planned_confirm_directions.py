"""correct inverted directions on planned-confirm transfers (ADR-0032 amended)

Revision 0006 backfilled ``transfer_direction`` from the insertion-order
invariant "within a group, the lower id is the outgoing leg". That holds for
``transactions.transfer()`` and ``goals.contribute_to_goal()``, which persist
both legs in one ``add_all``, but it is inverted for
``planned._confirm_transfer()``: there the destination leg is the
pre-existing planned row (lower id) and the source leg is created at confirm
time (higher id). Those pairs were backfilled backwards, so deleting one
would move both balances the wrong way.

Such pairs are identified by their creation spread: legs written in a single
``add_all`` share a creation instant, while a planned row predates its
confirmation. Only two-leg groups whose creation instants differ by more than
``_SPREAD_SECONDS`` are corrected.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-31

"""
from datetime import datetime, timedelta
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SPREAD_SECONDS = 60


def _as_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _staggered_pairs() -> list[tuple[int, int]]:
    """(outgoing_id, incoming_id) per two-leg group created at distinct times."""
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, transfer_group_id, created_at FROM \"transaction\" "
            "WHERE transfer_group_id IS NOT NULL ORDER BY transfer_group_id, id"
        )
    ).fetchall()
    groups: dict[str, list[tuple[int, datetime | None]]] = {}
    for row in rows:
        groups.setdefault(row[1], []).append((row[0], _as_datetime(row[2])))
    pairs: list[tuple[int, int]] = []
    for legs in groups.values():
        if len(legs) != 2:
            continue
        (first_id, first_at), (second_id, second_at) = legs
        if first_at is None or second_at is None:
            continue
        if abs(second_at - first_at) <= timedelta(seconds=_SPREAD_SECONDS):
            continue
        if second_at > first_at:
            pairs.append((second_id, first_id))
        else:
            pairs.append((first_id, second_id))
    return pairs


def _apply(pairs: list[tuple[int, int]]) -> None:
    conn = op.get_bind()
    for outgoing_id, incoming_id in pairs:
        conn.execute(
            sa.text(
                "UPDATE \"transaction\" SET transfer_direction = 'out' WHERE id = :id"
            ),
            {"id": outgoing_id},
        )
        conn.execute(
            sa.text(
                "UPDATE \"transaction\" SET transfer_direction = 'in_' WHERE id = :id"
            ),
            {"id": incoming_id},
        )


def upgrade() -> None:
    _apply(_staggered_pairs())


def downgrade() -> None:
    _apply([(incoming, outgoing) for outgoing, incoming in _staggered_pairs()])
