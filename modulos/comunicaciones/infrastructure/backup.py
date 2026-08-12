"""Respaldo y restauración locales de BC Comunicaciones.

Backup: copia SQLite consistente con retención. Restore: valida la copia, deja
una copia de seguridad del estado actual antes de pisarlo y recién entonces
restaura. Nunca se pierde el estado previo por un restore equivocado.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence
from urllib.parse import quote

from ..domain.errors import BackupError, RestoreError
from .sqlite_repository import REQUIRED_TABLES, SQLiteCommunicationsRepository


BACKUP_PREFIX = "bc-comunicaciones"


@dataclass(frozen=True)
class RestoreResult:
    restored_from: Path
    safety_backup: Path
    templates: int
    prepared_messages: int


class LocalBackupService:
    def __init__(
        self,
        repository: SQLiteCommunicationsRepository,
        backup_directory: str | Path,
        *,
        keep: int = 30,
    ) -> None:
        self.repository = repository
        self.backup_directory = Path(backup_directory)
        self.keep = keep

    def create_backup(self, label: str = "manual", *, protect: Path | None = None) -> Path:
        """Crea una copia y aplica retención.

        `protect` marca una copia que la retención no puede borrar: se usa al
        restaurar, donde el archivo de origen está en esta misma carpeta.
        """
        safe_label = "".join(char for char in str(label or "manual") if char.isalnum() or char in "-_") or "manual"
        try:
            self.backup_directory.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            destination = self.backup_directory / f"{BACKUP_PREFIX}-{safe_label}-{timestamp}.sqlite3"
            self.repository.backup_to(destination)
        except (OSError, sqlite3.Error) as error:
            raise BackupError(f"No se pudo crear la copia de seguridad: {error}") from error
        self._apply_retention(protect=(destination, protect))
        return destination

    def list_backups(self) -> Sequence[Path]:
        if not self.backup_directory.is_dir():
            return ()
        return tuple(
            sorted(
                self.backup_directory.glob(f"{BACKUP_PREFIX}-*.sqlite3"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        )

    def restore(self, source: str | Path) -> RestoreResult:
        source_path = Path(source).resolve()
        self.validate_backup(source_path)
        # La copia de seguridad previa vive en esta misma carpeta: hay que impedir
        # que su retención borre justamente el archivo que estamos por restaurar.
        safety = self.create_backup("previo-a-restaurar", protect=source_path)
        # Segunda validación: entre la primera y este punto se escribió en la
        # carpeta. Si el origen ya no está intacto, se aborta antes de tocar nada.
        try:
            self.validate_backup(source_path)
        except RestoreError as error:
            raise RestoreError(
                f"{error} Tus datos siguen intactos y hay una copia en: {safety}"
            ) from error
        try:
            self.repository.restore_from(source_path)
        except (OSError, sqlite3.Error) as error:
            # El estado previo quedó guardado en `safety`; se informa para poder volver.
            raise RestoreError(
                f"No se pudo restaurar. Tus datos anteriores siguen en: {safety}. Detalle: {error}"
            ) from error
        return RestoreResult(
            restored_from=source_path,
            safety_backup=safety,
            templates=self.repository.count_templates(),
            prepared_messages=self.repository.count_prepared_messages(),
        )

    @staticmethod
    def read_only_uri(source: Path) -> str:
        """URI SQLite de sólo lectura, con la ruta escapada.

        Sin escapar, una carpeta con `#` o `%` en el nombre (perfectamente
        legítima en un pendrive) rompía la apertura y el archivo se rechazaba
        como si no fuera una copia válida.
        """
        return f"file:{quote(source.as_posix(), safe='/:')}?mode=ro"

    @classmethod
    def validate_backup(cls, source: str | Path) -> None:
        source_path = Path(source)
        if not source_path.is_file():
            raise RestoreError(f"El archivo no existe: {source_path}")
        try:
            connection = sqlite3.connect(cls.read_only_uri(source_path), uri=True)
        except sqlite3.Error as error:
            raise RestoreError(f"El archivo no es una copia de BC Comunicaciones: {error}") from error
        try:
            if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RestoreError("La copia de seguridad está dañada.")
            present = {
                row[0]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
        except sqlite3.DatabaseError as error:
            raise RestoreError(f"El archivo no es una copia de BC Comunicaciones: {error}") from error
        finally:
            connection.close()
        missing = [table for table in REQUIRED_TABLES if table not in present]
        if missing:
            raise RestoreError(
                "El archivo elegido no es una copia de BC Comunicaciones "
                f"(faltan las tablas: {', '.join(missing)})."
            )

    def _apply_retention(self, *, protect: tuple[Path | None, ...] = ()) -> None:
        intocables = {path.resolve() for path in protect if path is not None}
        for expired in self.list_backups()[self.keep:]:
            if expired.resolve() in intocables:
                continue
            expired.unlink(missing_ok=True)
