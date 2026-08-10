"""Rutas estables de datos, independientes del cwd y del código fuente."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DATA_DIR_ENV = "BC_CAJA_DATA_DIR"


@dataclass(frozen=True)
class CashDataPaths:
    root: Path
    database: Path
    backups: Path
    logs: Path

    def ensure(self) -> "CashDataPaths":
        self.root.mkdir(parents=True, exist_ok=True)
        self.backups.mkdir(parents=True, exist_ok=True)
        self.logs.mkdir(parents=True, exist_ok=True)
        return self


def resolve_data_paths(environ: dict[str, str] | None = None) -> CashDataPaths:
    values = os.environ if environ is None else environ
    configured = values.get(DATA_DIR_ENV, "").strip()
    if configured:
        root = Path(configured).expanduser().resolve()
    elif values.get("LOCALAPPDATA"):
        root = Path(values["LOCALAPPDATA"]) / "BC" / "Caja"
    elif values.get("XDG_DATA_HOME"):
        root = Path(values["XDG_DATA_HOME"]) / "bc-caja"
    else:
        root = Path.home() / ".local" / "share" / "bc-caja"
    return CashDataPaths(
        root=root,
        database=root / "bc_caja.sqlite3",
        backups=root / "Backups",
        logs=root / "Logs",
    )
