"""Controller testeable entre la UI legacy y los servicios de BC Caja."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
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
from ..domain.models import CashDay, CashEntry, CashTotals, money, parse_business_date


@dataclass(frozen=True)
class ImportSummary:
    days: int
    entries: int


class CashDayUIController:
    def __init__(self, service: CashDayService, backup_service=None, movements_exporter=None) -> None:
        self.service = service
        self.backup_service = backup_service
        self.movements_exporter = movements_exporter
        self.last_backup_path: Path | None = None
        self.last_warning: str | None = None

    def load_day(self, date_text: str, unit: str) -> CashDay:
        return self.service.get_by_date_and_unit(date_text, unit)

    def open_or_load_day(self, date_text: str, unit: str, opening_cash: Any = None) -> CashDay:
        try:
            return self.load_day(date_text, unit)
        except CashDayNotFoundError:
            if opening_cash is None or (isinstance(opening_cash, str) and not opening_cash.strip()):
                opening_cash = self.service.suggested_opening_cash(
                    business_date=date_text, unit=unit
                )
                if opening_cash is None:
                    raise InvalidCashDayError("Ingresá la caja inicial para abrir este día.") from None
            return self.service.open_day(
                business_date=date_text, unit=unit, opening_cash=opening_cash
            )

    def open_or_load_day_with_notice(
        self, date_text: str, unit: str, opening_cash: Any = None
    ) -> tuple[CashDay, str | None]:
        """Abre con el monto visible o explica por qué se conserva una caja existente."""
        try:
            existing = self.load_day(date_text, unit)
        except CashDayNotFoundError:
            return self.open_or_load_day(date_text, unit, opening_cash), None
        if opening_cash is None or (isinstance(opening_cash, str) and not opening_cash.strip()):
            return existing, None
        requested = money(opening_cash, field_name="caja inicial")
        if requested == existing.opening_cash:
            return existing, None
        return existing, (
            "La caja de esta fecha ya fue abierta con caja inicial "
            f"{existing.opening_cash:,}.".replace(",", ".")
        )

    def add_manual_entry(self, values: Mapping[str, Any]) -> tuple[CashDay, CashEntry]:
        self._require_saleswoman(values)
        if "items" in values and not values.get("items"):
            raise InvalidCashDayError("Agregue al menos un producto antes de guardar.")
        entry = self._entry_from_legacy(values, origin="manual")
        cash_day = self.open_or_load_day(
            str(values.get("fecha", "")),
            str(values.get("unidad", "")),
            values.get("caja_inicial"),
        )
        saved = self.service.add_entry(cash_day.id, entry)
        return self.service.get_day(cash_day.id), saved

    def add_expense(
        self, date_text: str, unit: str, concept: str, amount: Any, observations: str = ""
    ) -> tuple[CashDay, CashEntry]:
        if not str(concept).strip():
            raise InvalidCashDayError("Ingresá el concepto del gasto.")
        cash_day = self.load_day(date_text, unit)
        entry = CashEntry(
            description=str(concept).strip(), expenses=amount,
            origin="manual-expense", source_reference=str(observations).strip(),
        )
        saved = self.service.add_entry(cash_day.id, entry)
        return self.service.get_day(cash_day.id), saved

    def add_withdrawal(
        self, date_text: str, unit: str, amount: Any,
        destination: str = "Administración", observations: str = "",
        performed_by: str = "",
    ) -> tuple[CashDay, CashEntry]:
        cash_day = self.load_day(date_text, unit)
        saved = self.service.record_withdrawal(
            cash_day.id, amount, destination, observations, performed_by
        )
        return self.service.get_day(cash_day.id), saved

    @staticmethod
    def opening_difference_message(cash_day: CashDay) -> str | None:
        difference = cash_day.initial_cash_difference
        if difference is None or difference == 0:
            return None
        amount = f"{abs(difference):,}".replace(",", ".")
        return (
            f"⚠ Caja inicial con diferencia — {'sobran' if difference > 0 else 'faltan'} "
            f"{amount}"
        )

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
        cash_day = self.service.close_day(self.load_day(date_text, unit).id)
        warnings = []
        if self.movements_exporter is not None:
            try:
                self.movements_exporter.sync_closed_day(cash_day)
            except OSError:
                warnings.append(
                    "La Caja quedó cerrada, pero no se pudo integrar el cierre con Movimientos."
                )
        if self.backup_service is not None:
            try:
                self.last_backup_path = self.backup_service.create_backup("cierre")
            except (OSError, sqlite3.Error):
                warnings.append(
                    "La Caja quedó cerrada y guardada, pero no se pudo crear el backup local."
                )
        self.last_warning = " ".join(warnings) or None
        return cash_day

    def sync_closed_day_with_movements(self, date_text: str, unit: str):
        """Reintento seguro para una integración interrumpida o ya aplicada."""
        if self.movements_exporter is None:
            raise InvalidCashDayError("la integración con Movimientos no está configurada")
        return self.movements_exporter.sync_closed_day(self.load_day(date_text, unit))

    def create_backup(self, label: str = "manual") -> Path:
        if self.backup_service is None:
            raise InvalidCashDayError("el servicio de backup no está configurado")
        self.last_backup_path = self.backup_service.create_backup(label)
        return self.last_backup_path

    def update_manual_entry(
        self, entry_id: str, values: Mapping[str, Any], *, reason: str = "", user: str = ""
    ) -> tuple[CashDay, CashEntry]:
        self._require_saleswoman(values)
        if "items" in values and not values.get("items"):
            raise InvalidCashDayError(
                "La venta editada no puede quedar sin productos; cancelá o anulá la venta."
            )
        cash_day = self.load_day(str(values.get("fecha", "")), str(values.get("unidad", "")))
        existing = next((entry for entry in cash_day.entries if entry.id == entry_id), None)
        if existing is None:
            raise InvalidCashDayError(f"movimiento inexistente: {entry_id}")
        candidate = self._entry_from_legacy(values, origin=existing.origin)
        total_pagos = (
            (candidate.cash or 0)
            + (candidate.card_check or 0)
            + (candidate.agreement_amount or 0)
        )
        if candidate.total is not None and total_pagos > candidate.total:
            raise InvalidCashDayError(
                "Los pagos cargados exceden el nuevo total de la venta. "
                "Ajustá efectivo, tarjeta/transferencia o monto convenio."
            )
        updated = existing.edited(
            description=candidate.description,
            envelope=candidate.envelope,
            frame_origin=candidate.frame_origin,
            code=candidate.code,
            frame=candidate.frame,
            lens=candidate.lens,
            laboratory=candidate.laboratory,
            prescription_doctor=candidate.prescription_doctor,
            total=candidate.total,
            cash=candidate.cash,
            card_check=candidate.card_check,
            orders=candidate.orders,
            agreement_amount=candidate.agreement_amount,
            installments=candidate.installments,
            balance=candidate.balance,
            expenses=candidate.expenses,
            source_reference=candidate.source_reference,
            customer_document=candidate.customer_document,
            customer_phone=candidate.customer_phone,
            saleswoman=candidate.saleswoman,
            delivery_date=candidate.delivery_date,
            observations=candidate.observations,
            items=candidate.items,
        )
        saved = self.service.update_entry(
            cash_day.id, updated, reason=str(reason).strip(), user=str(user).strip()
        )
        return self.service.get_day(cash_day.id), saved

    def void_entry(self, date_text: str, unit: str, entry_id: str, reason: str) -> CashDay:
        cash_day = self.load_day(date_text, unit)
        self.service.void_entry(cash_day.id, entry_id, reason)
        return self.service.get_day(cash_day.id)

    def list_history(self, date_text: str, unit: str) -> CashDay:
        return self.load_day(date_text, unit)

    def list_history_range(self, start_text: str, end_text: str, unit: str):
        start = parse_business_date(start_text)
        end = parse_business_date(end_text)
        if start > end:
            raise InvalidCashDayError("Desde debe ser anterior o igual a Hasta.")
        return self.service.repository.list_between(start, end, unit)

    def correct_opening_cash(
        self, date_text: str, unit: str, new_value: Any, reason: str, user: str
    ) -> CashDay:
        day = self.load_day(date_text, unit)
        parsed = money(new_value, field_name="caja inicial")
        if not str(reason or "").strip():
            raise InvalidCashDayError("El motivo de la corrección es obligatorio.")
        if not str(user or "").strip():
            raise InvalidCashDayError("El usuario de la corrección es obligatorio.")
        return self.service.repository.correct_opening_cash(
            day.id, parsed, str(reason).strip(), str(user).strip()
        )

    def opening_cash_corrections(self, cash_day_id: str):
        return self.service.repository.list_day_corrections(cash_day_id)

    def record_cash_count(self, date_text: str, unit: str, quantities: Mapping[int, int]):
        return self.service.record_cash_count(self.load_day(date_text, unit).id, quantities)

    def latest_cash_count(self, cash_day_id: str):
        return self.service.repository.get_latest_cash_count(cash_day_id)

    def list_orders(self, filter_name: str = "Todos", today=None):
        return self.service.list_orders(filter_name=filter_name, today=today)

    def update_order_status(self, order_id: str, status: str):
        return self.service.update_order_status(order_id, status)

    def order_counts(self, today=None) -> tuple[int, int]:
        return (
            len(self.list_orders("Hoy", today=today)),
            len(self.list_orders("Atrasados", today=today)),
        )

    @staticmethod
    def _require_saleswoman(values: Mapping[str, Any]) -> None:
        saleswoman = str(values.get("vendedora", "")).strip()
        if not saleswoman or saleswoman == "Seleccionar...":
            raise InvalidCashDayError("Seleccione la vendedora antes de guardar.")

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
            laboratory=values.get("laboratorio", ""),
            prescription_doctor=values.get("receta_dr", ""),
            total=values.get("total"),
            cash=values.get("efectivo"),
            card_check=values.get("tarjeta_cheque"),
            orders=values.get("ordenes", ""),
            agreement_amount=values.get("monto_convenio"),
            installments=values.get("cuotas", ""),
            balance=values.get("saldo", ""),
            expenses=values.get("gastos"),
            origin=origin,
            source_reference=source_reference or values.get("notas", ""),
            customer_document=values.get("cliente_documento", ""),
            customer_phone=values.get("cliente_telefono", ""),
            saleswoman=values.get("vendedora", ""),
            delivery_date=values.get("fecha_entrega") or None,
            observations=values.get("notas", ""),
            items=tuple(values.get("items") or ()),
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
