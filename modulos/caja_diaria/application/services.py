"""Servicios de aplicación para orquestar el dominio y el repositorio."""

from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Mapping, Sequence

from .ports import CashDayRepository, CarryForwardPolicy
from ..domain.errors import CashDayAlreadyExistsError, CashDayNotFoundError
from ..domain.models import CashCount, CashDay, CashEntry, CashTotals, parse_business_date


class CashDayService:
    def __init__(self, repository: CashDayRepository) -> None:
        self.repository = repository

    def open_day(self, *, business_date: date | str, unit: str, opening_cash: int | str) -> CashDay:
        parsed_date = parse_business_date(business_date)
        normalized_unit = unit.strip().upper()
        if self.repository.get_by_date_and_unit(parsed_date, normalized_unit) is not None:
            raise CashDayAlreadyExistsError(
                f"ya existe una Caja para {parsed_date.isoformat()} / {normalized_unit}"
            )
        cash_day = CashDay.open(date=parsed_date, unit=normalized_unit, opening_cash=opening_cash)
        self.repository.save(cash_day)
        return cash_day

    def open_day_with_entries(
        self,
        *,
        business_date: date | str,
        unit: str,
        opening_cash: int | str,
        entries: Iterable[CashEntry],
    ) -> CashDay:
        """Crea y persiste un día completo en una sola escritura atómica."""
        parsed_date = parse_business_date(business_date)
        normalized_unit = unit.strip().upper()
        if self.repository.get_by_date_and_unit(parsed_date, normalized_unit) is not None:
            raise CashDayAlreadyExistsError(
                f"ya existe una Caja para {parsed_date.isoformat()} / {normalized_unit}"
            )
        cash_day = CashDay.open(date=parsed_date, unit=normalized_unit, opening_cash=opening_cash)
        cash_day.replace_entries(entries)
        self.repository.save(cash_day)
        return cash_day

    def get_day(self, cash_day_id: str) -> CashDay:
        cash_day = self.repository.get(cash_day_id)
        if cash_day is None:
            raise CashDayNotFoundError(f"Caja inexistente: {cash_day_id}")
        return cash_day

    def get_by_date_and_unit(self, business_date: date | str, unit: str) -> CashDay:
        cash_day = self.repository.get_by_date_and_unit(parse_business_date(business_date), unit.strip().upper())
        if cash_day is None:
            raise CashDayNotFoundError(f"Caja inexistente: {business_date} / {unit}")
        return cash_day

    def list_between(
        self, start_date: date | str, end_date: date | str, unit: str | None = None
    ) -> Sequence[CashDay]:
        return self.repository.list_between(
            parse_business_date(start_date),
            parse_business_date(end_date),
            unit.strip().upper() if unit else None,
        )

    def add_entry(self, cash_day_id: str, entry: CashEntry) -> CashEntry:
        cash_day = self.get_day(cash_day_id)
        assigned = cash_day.add_entry(entry)
        self.repository.save(cash_day)
        return assigned

    def update_entry(self, cash_day_id: str, entry: CashEntry) -> CashEntry:
        cash_day = self.get_day(cash_day_id)
        updated = cash_day.update_entry(entry)
        self.repository.save(cash_day)
        return updated

    def remove_entry(self, cash_day_id: str, entry_id: str) -> None:
        cash_day = self.get_day(cash_day_id)
        cash_day.remove_entry(entry_id)
        self.repository.save(cash_day)

    def import_entries(self, cash_day_id: str, entries: Iterable[CashEntry]) -> CashDay:
        """Reemplaza el lote completo en una única operación de repositorio."""
        cash_day = self.get_day(cash_day_id)
        cash_day.replace_entries(entries)
        self.repository.save(cash_day)
        return cash_day

    def totals(self, cash_day_id: str) -> CashTotals:
        return self.get_day(cash_day_id).totals()

    def close_day(self, cash_day_id: str, *, closed_at: datetime | None = None) -> CashDay:
        cash_day = self.get_day(cash_day_id)
        cash_day.close(closed_at=closed_at)
        self.repository.save(cash_day)
        return cash_day

    def record_cash_count(self, cash_day_id: str, quantities: Mapping[int, int]) -> CashCount:
        cash_count = self.get_day(cash_day_id).count_cash(quantities)
        self.repository.save_cash_count(cash_count)
        return cash_count
