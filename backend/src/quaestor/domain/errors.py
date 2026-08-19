"""Typed domain errors. P1 maps these to 4xx; P2 surfaces them as agent text."""


class QuaestorError(Exception):
    """Base class for all Quaestor domain errors.

    Args:
        message: the English detail this error has always carried.
        code: stable snake_case identifier a client can key a translation
            catalog on; `None` for a site not yet migrated (ADR-0059).
        data: the values a translated message needs to interpolate.
    """

    def __init__(self, message: str, *, code: str | None = None, data: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data or {}


class ValidationError(QuaestorError):
    """Invalid input: amount <= 0, unsupported currency, archived id, invalid type."""


def require_positive(amount: int) -> None:
    """A movement is worth something or it is not a movement (AC-24)."""
    if amount <= 0:
        raise ValidationError("amount must be > 0", code="amount_not_positive")


class MissingRate(QuaestorError):
    """No TRM set: a read needing base-currency figures must fail loud (AC-9)."""


class TransferImbalance(QuaestorError):
    """Invalid transfer: source == destination or the pair does not balance."""


class NotFound(QuaestorError):
    """Nonexistent id in a read or write operation."""


class IllegalTransition(QuaestorError):
    """A status transition that is not allowed (e.g. confirm/skip a non-planned tx)."""


class CorrectionNotApplied(QuaestorError):
    """A correction's arithmetic did not prove out, so none of it was kept.

    Raised when a balance did not move by exactly the delta the correction
    declared — including not moving at all. Distinct from ValidationError: the
    input was fine and the write is what failed (ADR-0051)."""
