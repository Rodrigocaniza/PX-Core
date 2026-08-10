"""Composition root mínimo, todavía no conectado a CustomTkinter."""

from __future__ import annotations

from pathlib import Path

from .application.services import CashDayService
from .infrastructure.sqlite_repository import SQLiteCashDayRepository


DEFAULT_DATABASE = Path("Datos") / "bc_caja.sqlite3"


def build_cash_day_service(database_path: str | Path = DEFAULT_DATABASE) -> CashDayService:
    return CashDayService(SQLiteCashDayRepository(database_path))
