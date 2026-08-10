"""Errores explícitos del dominio de Caja Diaria."""


class CashDayError(ValueError):
    """Base para violaciones del contrato de Caja."""


class InvalidMoneyError(CashDayError):
    """Un valor monetario no es un entero PYG válido."""


class InvalidCashDayError(CashDayError):
    """La fecha, unidad o transición de Caja es inválida."""


class CashDayClosedError(CashDayError):
    """Se intentó mutar una Caja cerrada."""


class CashDayAlreadyExistsError(CashDayError):
    """Ya existe una Caja para fecha y unidad."""


class CashDayNotFoundError(CashDayError):
    """No existe la Caja solicitada."""


class InvalidCashCountError(CashDayError):
    """El conteo físico contiene cantidades inválidas."""
