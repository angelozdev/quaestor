"""App-wide date display format shared by the MCP renderer and the markdown
report renderer. Keep in sync with `frontend/lib/date.ts`.

Format: 'Sun, 10 May 2026'. For storage and input parsing use ISO
(`datetime.date.isoformat`); this is purely for human rendering.
"""
from __future__ import annotations

from datetime import date as Date

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def display_date(d: Date) -> str:
    """Render a date as 'Sun, 10 May 2026' (app-wide display format)."""
    return f"{WEEKDAYS[d.weekday()]}, {d.day} {MONTHS[d.month]} {d.year}"
