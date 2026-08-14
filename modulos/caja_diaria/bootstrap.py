"""Composition root de BC Caja, consumido por la UI CustomTkinter legacy."""

from __future__ import annotations

import os
from pathlib import Path

from .application.services import CashDayService
from .application.admin_ops import AdminOperations
from .application.carry_forward import PreviousClosedDayCarryForwardPolicy
from .config import DATA_DIR_ENV, CashDataPaths, resolve_data_paths
from .infrastructure.backup import LocalBackupService
from .infrastructure.sqlite_repository import SQLiteCashDayRepository
from .infrastructure.movements_exporter import LegacyMovementsExporter
from .ui.controller import CashDayUIController


def build_cash_day_service(database_path: str | Path | None = None) -> CashDayService:
    path = Path(database_path) if database_path is not None else resolve_data_paths().ensure().database
    repository = SQLiteCashDayRepository(path)
    repository.integrity_check()
    return CashDayService(repository, PreviousClosedDayCarryForwardPolicy())


def build_cash_day_controller(
    database_path: str | Path | None = None,
    *,
    data_paths: CashDataPaths | None = None,
) -> CashDayUIController:
    explicit_data_location = (
        data_paths is not None
        or database_path is not None
        or bool(os.environ.get(DATA_DIR_ENV, "").strip())
    )
    if data_paths is not None:
        paths = data_paths
    elif database_path is not None:
        explicit_database = Path(database_path)
        paths = CashDataPaths(
            root=explicit_database.parent,
            database=explicit_database,
            backups=explicit_database.parent / "Backups",
            logs=explicit_database.parent / "Logs",
        )
    else:
        paths = resolve_data_paths()
    if database_path is None:
        paths.ensure()
        database_path = paths.database
    service = build_cash_day_service(database_path)
    backup = LocalBackupService(service.repository, paths.backups)
    movements_path = (
        paths.root / "movimientos.txt"
        if explicit_data_location
        else Path(__file__).resolve().parents[2] / "Datos" / "movimientos.txt"
    )
    movements = LegacyMovementsExporter(movements_path)
    return CashDayUIController(
        service, backup_service=backup, movements_exporter=movements,
        admin_operations=AdminOperations(service.repository, paths.root),
    )
