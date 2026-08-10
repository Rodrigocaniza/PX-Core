"""Controller testeable entre la UI legacy y los servicios de BC Caja."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Mapping

from ..application.services import CashDayService
from ..domain.errors import (
    CashDayAlreadyExistsError,
    CashDayClosedError,
    CashDayNotFoundError,
    InvalidCashCountError,
    InvalidCashDayError,
    InvalidMoneyError,
)
from ..domain.models import CashDay, CashEntry, CashTotals


@dataclass(frozen=True)
class ImportSummary:
    days: int
    entries: int


class CashDayUIController:
    def __init__(self, service: CashDayService) -> None:
        self.service = service

    def load_day(self, date_text: str, unit: str) -> CashDay:
        return self.service.get_by_date_and_unit(date_text, unit)

    def open_or_load_day(self, date_text: str, unit: str, opening_cash: Any = None) -> CashDay:
        try:
            return self.load_day(date_text, unit)
        except CashDayNotFoundError:
            if opening_cash is None or (isinstance(opening_cash, str) and not opening_cash.strip()):
                raise InvalidCashDayError("Ingresá la caja inicial para abrir este día.") from None
            return self.service.open_day(
                business_date=date_text, unit=unit, opening_cash=opening_cash
            )

    def add_manual_entry(self, values: Mapping[str, Any]) -> tuple[CashDay, CashEntry]:
        entry = self._entry_from_legacy(values, origin="manual")
        cash_day = self.open_or_load_day(
            str(values.get("fecha", "")),
            str(values.get("unidad", "")),
            values.get("caja_inicial"),
        )
        saved = self.service.add_entry(cash_day.id, entry)
        return self.service.get_day(cash_day.id), saved

    def import_legacy_analysis(self, result: Mapping[str, Any]) -> ImportSummary:
        imported_days = 0
        imported_entries = 0
        for date_text, day_data in result.get("por_dia", {}).items():
            entries = [
                self._entry_from_legacy(record, origin="excel", source_reference=day_data.get("hoja", ""))
                for record in day_data.get("registros", [])
            ]
            self.service.open_day_with_entries(
                business_date=date_text,
                unit=day_data.get("unidad", "PC"),
                opening_cash=day_data.get("caja_inicial", 0),
                entries=entries,
            )
            imported_days += 1
            imported_entries += len(entries)
        return ImportSummary(imported_days, imported_entries)

    def totals(self, date_text: str, unit: str) -> CashTotals:
        return self.load_day(date_text, unit).totals()

    def close_day(self, date_text: str, unit: str) -> CashDay:
        return self.service.close_day(self.load_day(date_text, unit).id)

    def record_cash_count(self, date_text: str, unit: str, quantities: Mapping[int, int]):
        return self.service.record_cash_count(self.load_day(date_text, unit).id, quantities)

    @staticmethod
    def _entry_from_legacy(
        values: Mapping[str, Any], *, origin: str, source_reference: str = ""
    ) -> CashEntry:
        return CashEntry(
            description=str(values.get("descripcion", "")),
            envelope=values.get("sobre", ""),
            frame_origin=values.get("arm_org", ""),
            code=values.get("cod", ""),
            frame=values.get("armazon", ""),
            lens=values.get("cristal", ""),
            prescription_doctor=values.get("receta_dr", ""),
            total=values.get("total"),
            cash=values.get("efectivo"),
            card_check=values.get("tarjeta_cheque"),
            orders=values.get("ordenes", ""),
            installments=values.get("cuotas", ""),
            balance=values.get("saldo", ""),
            expenses=values.get("gastos"),
            origin=origin,
            source_reference=source_reference,
        )


def friendly_error(error: Exception) -> tuple[str, str]:
    if isinstance(error, InvalidMoneyError):
        return "Importe inválido", str(error)
    if isinstance(error, InvalidCashCountError):
        return "Arqueo inválido", str(error)
    if isinstance(error, CashDayClosedError):
        return "Caja cerrada", "La Caja de ese día está cerrada y no admite modificaciones."
    if isinstance(error, CashDayAlreadyExistsError):
        return "Caja ya existente", str(error)
    if isinstance(error, CashDayNotFoundError):
        return "Caja inexistente", "No existe una Caja abierta o cerrada para esa fecha y unidad."
    if isinstance(error, InvalidCashDayError):
        return "Datos inválidos", str(error)
    if isinstance(error, sqlite3.Error):
        return "No se pudo guardar", "SQLite no pudo completar la operación. Tus datos siguen en pantalla."
    return "No se pudo completar", "Ocurrió un error inesperado. Tus datos siguen en pantalla."
