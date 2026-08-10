"""Regla de arrastre confirmada por el libro operativo real."""

from datetime import date
from .ports import CarryForwardPolicy
from ..domain.models import CashDay


class PreviousClosedDayCarryForwardPolicy(CarryForwardPolicy):
    """Arrastra el efectivo final congelado del ultimo dia cerrado."""

    def opening_cash_for(self, previous_day: CashDay, next_date: date) -> int:
        if previous_day.business_date >= next_date:
            raise ValueError("el dia anterior debe preceder al nuevo dia operativo")
        if previous_day.closing_totals is None:
            raise ValueError("el dia anterior debe estar cerrado antes de arrastrar caja")
        return previous_day.closing_totals.expected_cash
