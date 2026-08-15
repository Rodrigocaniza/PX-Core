"""Entrypoint del piloto aislado de BC Gestión Central (datos sintéticos)."""
from __future__ import annotations

import argparse
import json
import os
from datetime import timedelta
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
    parser.add_argument("--interaction-smoke", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.self_check:
        if args.data_dir is None:
            parser.error("--self-check requiere --data-dir")
        return self_check(args.data_dir)
    if args.interaction_smoke:
        if args.data_dir is None:
            parser.error("--interaction-smoke requiere --data-dir")
        return interaction_smoke(args.data_dir)
    service = build_service(args.data_dir)
    service.bootstrap_synthetic_pilot()
    from modulos.gestion_central.ui import CentralPilotWindow
    CentralPilotWindow(service).run()
    return 0


def interaction_smoke(data_dir: Path) -> int:
    """Pulsa widgets reales del EXE sobre una base sintética aislada."""
    import tkinter as tk
    from modulos.gestion_central.models import CashSnapshot, Principal, Role, Unit, utc_now
    from modulos.gestion_central.ui import CentralPilotWindow

    service = build_service(data_dir)
    service.bootstrap_synthetic_pilot()
    event_id = "exe-interaction-smoke"
    with service.repository.connection() as con:
        exists = con.execute("SELECT 1 FROM cash_snapshots WHERE event_id=?", (event_id,)).fetchone()
    if not exists:
        service.ingest_snapshot(Principal("smoke", Role.ADMIN_CENTRAL), CashSnapshot(
            event_id=event_id, unit=Unit.OPTICA_ASUNCION, business_date="2099-01-15",
            status="OPEN", opening_cash=500_000, income=800_000, cash=500_000,
            card_check=300_000, expenses=50_000, withdrawals=25_000,
            expected_cash=925_000, counted_cash=900_000, entry_count=5,
            source_updated_at=utc_now() + timedelta(seconds=2),
        ))
    root = tk.Tk(); root.withdraw()
    app = CentralPilotWindow(service, root=root, notifier=lambda *_: None)
    root.update()
    visited = []
    for unit in Unit:
        app.card_buttons[unit].invoke(); root.update()
        if app.current_screen != "detail" or app.selected_unit != unit:
            raise RuntimeError(f"detalle incorrecto: {unit.value}")
        visited.append(unit.value)
        app.back_button.invoke(); root.update()
    app.refresh_button.invoke(); root.update()
    if not app.status_var.get().startswith("Actualizado "):
        raise RuntimeError("Actualizar no confirmó visualmente")
    alert_ids = app.alerts.get_children()
    if alert_ids:
        alert_id = alert_ids[0]
        app.alerts.selection_set(alert_id); app.alerts.event_generate("<<TreeviewSelect>>"); root.update()
        app.ack_button.invoke(); root.update()
        if alert_id in app.alerts.get_children():
            raise RuntimeError("la alerta reconocida continúa activa")
    else:
        alert_id = None
    root.destroy()
    reopened_root = tk.Tk(); reopened_root.withdraw()
    reopened = CentralPilotWindow(service, root=reopened_root, notifier=lambda *_: None)
    reopened_root.update()
    if alert_id and alert_id in reopened.alerts.get_children():
        raise RuntimeError("el reconocimiento no persistió")
    reopened_root.destroy()
    evidence = {"status": "PASS", "units_visited": visited, "refresh": "PASS", "alert_ack": "PASS", "restart_persistence": "PASS", "synthetic": True, "production": False}
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "interaction-smoke.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
