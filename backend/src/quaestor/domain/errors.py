"""Typed domain errors. P1 maps these to 4xx; P2 surfaces them as agent text."""


class QuaestorError(Exception):
    """Base class for all Quaestor domain errors."""


class ValidationError(QuaestorError):
    """Invalid input: amount <= 0, unsupported currency, archived id, invalid type."""


class MissingRate(QuaestorError):
    """No TRM set: a read needing base-currency figures must fail loud (AC-9)."""


class TransferImbalance(QuaestorError):
    """Invalid transfer: source == destination or the pair does not balance."""


class NotFound(QuaestorError):
    """Nonexistent id in a read or write operation."""


class IllegalTransition(QuaestorError):
    """A status transition that is not allowed (e.g. confirm/skip a non-planned tx)."""
