"""Declaring repeating obligations in tests, with the intent spelled out."""

from quaestor.services import recurring


def declare_existing(session, **fields):
    """An obligation the user set up on or before its start date.

    Nothing had already fallen due when it entered the system, so the engine
    charges its missed dates unattended — the catch-up AC-9 describes.

    The other case is an obligation declared when its start is already behind:
    those dates are offered for the user to accept or decline instead (AC-12).
    A test that wants that one passes `declared_on` itself.
    """
    fields.setdefault("declared_on", fields["start_date"])
    return recurring.create_recurring(session, **fields)
