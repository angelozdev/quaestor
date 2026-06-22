"""Daily orchestration entry point (ADR-011/017/020 + ADR-0013).

Runs three idempotent jobs in order:
  1. FX rate fetch (best-effort; failure does not block).
  2. materialize_due(today) — turns recurring items into transactions.
  3. ensure_month_closed(today) — closes the calendar month via rollover hooks.

Re-runs on the same day are no-ops by construction (ADR-017/020). A missed
day self-heals on the next run.
"""
from __future__ import annotations

import logging
import os
from datetime import date as Date
from decimal import Decimal

from sqlmodel import Session

from .. import db
from ..services.fx import set_fx_rate
from ..services.recurring import materialize_due
from ..services.rollover import ensure_month_closed
from .fx_fetch import fetch_usd_cop

log = logging.getLogger(__name__)


def run_daily(
    session: Session, today: Date, fx_url: str, fx_key: str | None
) -> dict:
    """Run the three daily jobs. Returns a small report dict (no secrets).

    Args:
        session: An open SQLModel session.
        today: The "as-of" date for materialization and month close.
        fx_url: FX provider URL. Empty string skips FX fetch entirely.
        fx_key: Optional FX provider API key.

    Returns:
        dict with keys: fx_rate (Decimal|None), fx_error (str|None),
        materialized_count (int), month_closed (str "YYYY-MM").
    """
    report: dict = {
        "fx_rate": None,
        "fx_error": None,
        "materialized_count": 0,
        "month_closed": f"{today.year:04d}-{today.month:02d}",
    }

    if fx_url:
        try:
            rate = fetch_usd_cop(fx_url, fx_key)
            set_fx_rate(session, today, rate)
            report["fx_rate"] = rate
        except Exception as exc:  # FX failures are non-fatal (ADR-011)
            log.exception("FX fetch failed; continuing")
            report["fx_error"] = repr(exc)

    occurrences = materialize_due(session, today)
    report["materialized_count"] = len(occurrences)

    ensure_month_closed(session, today)
    return report


def main() -> None:
    import json as _json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    fx_url = os.environ.get("FX_API_URL", "")
    fx_key = os.environ.get("FX_API_KEY") or None
    today = Date.today()
    with db.get_session() as session:
        report = run_daily(session, today, fx_url, fx_key)
    # Decimal is not JSON-native; stringify for the printed line.
    printable = {**report, "fx_rate": str(report["fx_rate"]) if report["fx_rate"] is not None else None}
    print(_json.dumps(printable, sort_keys=True))


if __name__ == "__main__":
    main()
