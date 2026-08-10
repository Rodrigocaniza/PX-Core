"""Puertos de aplicación; no dependen de SQLite ni de la UI."""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping, Protocol, Sequence

from ..domain.models import CashCount, CashDay


class CashDayRepository(Protocol):
    def save(self, cash_day: CashDay) -> None: ...

    def get(self, cash_day_id: str) -> CashDay | None: ...

    def get_by_date_and_unit(self, business_date: date, unit: str) -> CashDay | None: ...

    def list_between(self, start_date: date, end_date: date, unit: str | None = None) -> Sequence[CashDay]: ...

    def get_latest_closed_before(self, business_date: date, unit: str) -> CashDay | None: ...

    def save_cash_count(self, cash_count: CashCount) -> None: ...

    def get_latest_cash_count(self, cash_day_id: str) -> CashCount | None: ...

    def list_entry_revisions(self, entry_id: str) -> Sequence[Mapping[str, Any]]: ...


class CarryForwardPolicy(Protocol):
    """Boundary deliberadamente sin implementación hasta decisión de negocio."""

    def opening_cash_for(self, previous_day: CashDay, next_date: date) -> int: ...
