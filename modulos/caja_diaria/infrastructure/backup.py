"""Backup SQLite liviano para operación local."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .sqlite_repository import SQLiteCashDayRepository


class LocalBackupService:
    def __init__(
        self,
        repository: SQLiteCashDayRepository,
        backup_directory: str | Path,
        *,
        keep: int = 30,
    ) -> None:
        self.repository = repository
        self.backup_directory = Path(backup_directory)
        self.keep = keep

    def create_backup(self, label: str = "cierre") -> Path:
        self.backup_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        destination = self.backup_directory / f"bc-caja-{label}-{timestamp}.sqlite3"
        self.repository.backup_to(destination)
        self._apply_retention()
        return destination

    def _apply_retention(self) -> None:
        backups = sorted(
            self.backup_directory.glob("bc-caja-*.sqlite3"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for expired in backups[self.keep:]:
            expired.unlink(missing_ok=True)
