"""Errores tipados del dominio. P1 los mapea a 4xx; P2 a texto para el agente."""


class QuaestorError(Exception):
    """Base de todos los errores de dominio de Quaestor."""


class ValidationError(QuaestorError):
    """Entrada inválida: monto ≤ 0, moneda no soportada, id archivado, tipo inválido."""


class MissingRate(QuaestorError):
    """Falta tasa usd_cop para una tx no-COP sin fx_rate explícito."""


class TransferImbalance(QuaestorError):
    """Transferencia inválida: origen == destino o el par no cuadra."""


class NotFound(QuaestorError):
    """Id inexistente en una lectura o escritura."""
