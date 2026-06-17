"""Typed domain errors. P1 maps these to 4xx; P2 surfaces them as agent text."""


class QuaestorError(Exception):
    """Base class for all Quaestor domain errors."""


class ValidationError(QuaestorError):
    """Invalid input: amount <= 0, unsupported currency, archived id, invalid type."""


class MissingRate(QuaestorError):
    """Missing usd_cop rate for a non-COP transaction without an explicit fx_rate."""


class TransferImbalance(QuaestorError):
    """Invalid transfer: source == destination or the pair does not balance."""


class NotFound(QuaestorError):
    """Nonexistent id in a read or write operation."""
