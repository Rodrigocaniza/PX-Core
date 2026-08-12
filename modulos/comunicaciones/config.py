"""Rutas estables de datos de BC Comunicaciones.

Los datos viven fuera del código y fuera del directorio de trabajo, de modo que
actualizar o reinstalar la aplicación nunca los toca. Mismo criterio que BC Caja,
pero con carpeta y variable propias: un restore de Comunicaciones no puede
afectar los datos de Caja.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DATA_DIR_ENV = "BC_COMUNICACIONES_DATA_DIR"


@dataclass(frozen=True)
class CommunicationsDataPaths:
    root: Path
    database: Path
    backups: Path
    logs: Path

    def ensure(self) -> "CommunicationsDataPaths":
        self.root.mkdir(parents=True, exist_ok=True)
        self.backups.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        return self


def resolve_data_paths(environ: dict[str, str] | None = None) -> CommunicationsDataPaths:
    values = os.environ if environ is None else environ
    configured = values.get(DATA_DIR_ENV, "").strip()
    if configured:
        root = Path(configured).expanduser().resolve()
    elif values.get("LOCALAPPDATA"):
        root = Path(values["LOCALAPPDATA"]) / "BC" / "Comunicaciones"
    elif values.get("XDG_DATA_HOME"):
        root = Path(values["XDG_DATA_HOME"]) / "bc-comunicaciones"
    else:
        root = Path.home() / ".local" / "share" / "bc-comunicaciones"
    return CommunicationsDataPaths(
        root=root,
        database=root / "bc_comunicaciones.sqlite3",
        backups=root / "Backups",
        logs=root / "Logs",
    )
