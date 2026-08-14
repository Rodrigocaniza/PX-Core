"""Adaptador idempotente de cierres de BC Caja al TXT legacy de Movimientos."""

from __future__ import annotations

import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from ..domain.models import CashDay, CashDayStatus


_WRITE_LOCK = threading.Lock()


@dataclass(frozen=True)
class MovementExportResult:
    created: int
    existing: int


class LegacyMovementsExporter:
    """Publica el snapshot inmutable de un cierre sin duplicar su origen."""

    MARKER_PREFIX = "BC_CAJA"

    def __init__(self, movements_path: str | Path) -> None:
        self.movements_path = Path(movements_path)

    def sync_closed_day(self, cash_day: CashDay) -> MovementExportResult:
        if cash_day.status is not CashDayStatus.CLOSED or cash_day.closing_totals is None:
            raise ValueError("solo se puede integrar una Caja cerrada")

        totals = cash_day.closing_totals
        date_text = cash_day.business_date.strftime("%d-%m-%Y")
        candidates = []
        income = totals.cash + totals.card_check
        if income:
            candidates.append(
                self._line("Ingreso", date_text, "Externo", cash_day.unit, income, cash_day.id, "VENTAS")
            )
        if totals.expenses:
            candidates.append(
                self._line("Egreso", date_text, cash_day.unit, "Externo", totals.expenses, cash_day.id, "GASTOS")
            )

        with _WRITE_LOCK:
            existing_lines = self._read_lines()
            existing_markers = {
                part.strip()
                for line in existing_lines
                for part in line.split("|")
                if part.strip().startswith(f"{self.MARKER_PREFIX}:")
            }
            pending = [line for marker, line in candidates if marker not in existing_markers]
            if pending:
                self._atomic_write([*existing_lines, *pending])
        return MovementExportResult(created=len(pending), existing=len(candidates) - len(pending))

    def _line(
        self, movement_type: str, date_text: str, origin: str, destination: str,
        amount: int, cash_day_id: str, concept: str,
    ) -> tuple[str, str]:
        marker = f"{self.MARKER_PREFIX}:{cash_day_id}:{concept}"
        return marker, f"{movement_type}|{date_text}|{origin}|{destination}|{amount}|Si|{marker}"

    def _read_lines(self) -> list[str]:
        if not self.movements_path.exists():
            return []
        return self.movements_path.read_text(encoding="utf-8").splitlines()

    def _atomic_write(self, lines: list[str]) -> None:
        self.movements_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.movements_path.name}.", dir=self.movements_path.parent, text=True
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                if lines:
                    handle.write("\n".join(lines) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, self.movements_path)
        except BaseException:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass
            raise
