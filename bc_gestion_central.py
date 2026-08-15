"""Entrypoint del piloto aislado de BC Gestión Central (datos sintéticos)."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from modulos.gestion_central.models import Role
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import CentralManagementService


def default_data_dir() -> Path:
    configured = os.environ.get("BC_GESTION_CENTRAL_PILOT_DIR", "").strip()
    if configured:
        return Path(configured)
    return Path.home() / "BC Gestion Central Pilot"


def build_service(data_dir: Path | None = None) -> CentralManagementService:
    root = data_dir or default_data_dir()
    return CentralManagementService(CentralRepository(root / "gestion-central-pilot.sqlite3"))


def self_check(data_dir: Path) -> int:
    service = build_service(data_dir)
    service.bootstrap_synthetic_pilot()
    admin = service.authenticate("admin.piloto", "Piloto-Temporal-2026")
    dashboard = service.dashboard(admin)
    assert len(dashboard["cards"]) == 4
    assert admin.role == Role.ADMIN_CENTRAL
    print("BC_GESTION_CENTRAL_PILOT_OK units=4 synthetic=YES production=NO")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="BC Gestión Central - piloto aislado")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args(argv)
    if args.self_check:
        if args.data_dir is None:
            parser.error("--self-check requiere --data-dir")
        return self_check(args.data_dir)
    service = build_service(args.data_dir)
    service.bootstrap_synthetic_pilot()
    from modulos.gestion_central.ui import CentralPilotWindow
    CentralPilotWindow(service).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
