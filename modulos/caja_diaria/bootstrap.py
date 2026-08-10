"""Composition root de BC Caja, consumido por la UI CustomTkinter legacy."""

from __future__ import annotations

from pathlib import Path

from .application.services import CashDayService
from .config import CashDataPaths, resolve_data_paths
from .infrastructure.backup import LocalBackupService
from .infrastructure.sqlite_repository import SQLiteCashDayRepository
from .ui.controller import CashDayUIController


def build_cash_day_service(database_path: str | Path | None = None) -> CashDayService:
    path = Path(database_path) if database_path is not None else resolve_data_paths().ensure().database
    repository = SQLiteCashDayRepository(path)
    repository.integrity_check()
    return CashDayService(repository)


def build_cash_day_controller(
    database_path: str | Path | None = None,
    *,
    data_paths: CashDataPaths | None = None,
) -> CashDayUIController:
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
    return CashDayUIController(service, backup_service=backup)
