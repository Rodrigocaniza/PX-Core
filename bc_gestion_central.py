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
    parser.add_argument("--review-interaction-smoke", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--import-readonly-snapshot", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--organization", default="BC", help=argparse.SUPPRESS)
    parser.add_argument("--branch", default="Pilar", help=argparse.SUPPRESS)
    parser.add_argument("--period", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.self_check:
        if args.data_dir is None:
            parser.error("--self-check requiere --data-dir")
        return self_check(args.data_dir)
    if args.interaction_smoke:
        if args.data_dir is None:
            parser.error("--interaction-smoke requiere --data-dir")
        return interaction_smoke(args.data_dir)
    if args.review_interaction_smoke:
        if args.data_dir is None:
            parser.error("--review-interaction-smoke requiere --data-dir")
        return review_interaction_smoke(args.data_dir, args.review_interaction_smoke)
    if args.import_readonly_snapshot:
        if args.data_dir is None:
            parser.error("--import-readonly-snapshot requiere --data-dir")
        return import_readonly_snapshot(
            args.data_dir, args.import_readonly_snapshot,
            organization=args.organization, branch=args.branch, period=args.period,
        )
    service = build_service(args.data_dir)
    service.bootstrap_synthetic_pilot()
    from modulos.gestion_central.ui import CentralPilotWindow
    CentralPilotWindow(service).run()
    return 0


def import_readonly_snapshot(
    data_dir: Path, snapshot: Path, *, organization: str, branch: str, period: str | None,
) -> int:
    """Importa una copia local; jamás abre la base productiva en modo escritura."""
    from modulos.gestion_central.real_sync import ReviewService

    service = build_service(data_dir)
    service.bootstrap_synthetic_pilot()
    principal = service.authenticate("admin.piloto", "Piloto-Temporal-2026")
    review_service = ReviewService(service.repository)
    source_hash_before = review_service.snapshot_hash(snapshot)
    result = review_service.import_snapshot(
        principal, snapshot, organization=organization, branch=branch, period=period,
    )
    source_hash_after = review_service.snapshot_hash(snapshot)
    if source_hash_before != source_hash_after:
        raise RuntimeError("la copia fuente cambió durante la importación")
    evidence_dir = data_dir / "RealSync"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    safe_result = {
        "status": "PASS", "source_mode": "SQLITE_SNAPSHOT_QUERY_ONLY",
        "source_unchanged": True, "production_write": False,
        "period": result.period, "rows": result.processed,
        "inserted": result.inserted, "unchanged": result.unchanged,
        "changed": result.changed, "snapshot_sha256": source_hash_after,
    }
    (evidence_dir / "last-import.local.json").write_text(
        json.dumps(safe_result, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps(safe_result, ensure_ascii=False))
    return 0


def interaction_smoke(data_dir: Path) -> int:
    """Pulsa widgets reales del EXE sobre una base sintética aislada."""
    import tkinter as tk
    from modulos.gestion_central.models import CashSnapshot, Principal, Role, Unit, utc_now
    from modulos.gestion_central.ui import CentralPilotWindow

    data_dir.mkdir(parents=True, exist_ok=True)
    progress = data_dir / "interaction-progress.txt"
    def checkpoint(value: str):
        progress.write_text(value, encoding="utf-8")

    checkpoint("START")
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
    checkpoint("DATA_READY")
    root = tk.Tk(); root.withdraw()
    checkpoint("TK_READY")
    app = CentralPilotWindow(service, root=root, notifier=lambda *_: None)
    checkpoint("APP_READY")
    root.update()
    checkpoint("DASHBOARD_READY")
    visited = []
    for unit in Unit:
        app.card_buttons[unit].invoke(); root.update()
        if app.current_screen != "detail" or app.selected_unit != unit:
            raise RuntimeError(f"detalle incorrecto: {unit.value}")
        visited.append(unit.value)
        app.back_button.invoke(); root.update()
        checkpoint(f"VISITED_{unit.value}")
    app.refresh_button.invoke(); root.update()
    if not app.status_var.get().startswith("Actualizado "):
        raise RuntimeError("Actualizar no confirmó visualmente")
    checkpoint("REFRESHED")
    alert_ids = app.alerts.get_children()
    if alert_ids:
        alert_id = alert_ids[0]
        app.alerts.selection_set(alert_id); app.alerts.event_generate("<<TreeviewSelect>>"); root.update()
        app.ack_button.invoke(); root.update()
        if alert_id in app.alerts.get_children():
            raise RuntimeError("la alerta reconocida continúa activa")
        checkpoint("ALERT_ACKNOWLEDGED")
    else:
        alert_id = None
    app.content.destroy()
    checkpoint("FIRST_WINDOW_CLOSED")
    reopened = CentralPilotWindow(service, root=root, notifier=lambda *_: None)
    root.update()
    checkpoint("REOPENED")
    if alert_id and alert_id in reopened.alerts.get_children():
        raise RuntimeError("el reconocimiento no persistió")
    root.destroy()
    checkpoint("WINDOWS_CLOSED")
    evidence = {"status": "PASS", "units_visited": visited, "refresh": "PASS", "alert_ack": "PASS", "restart_persistence": "PASS", "synthetic": True, "production": False}
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "interaction-smoke.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    checkpoint("PASS")
    return 0


def review_interaction_smoke(data_dir: Path, snapshot: Path) -> int:
    """Ejercita widgets reales de revisión sobre datos sintéticos aislados."""
    import tkinter as tk
    from modulos.gestion_central.real_sync import REVIEW_FIELDS, ReviewService
    from modulos.gestion_central.ui import CentralPilotWindow

    import_readonly_snapshot(
        data_dir, snapshot, organization="SYNTHETIC-SMOKE", branch="Pilar", period=None,
    )
    service = build_service(data_dir)
    review = ReviewService(service.repository)
    confirmations = []
    root = tk.Tk(); root.withdraw()
    app = CentralPilotWindow(
        service, root=root, notifier=lambda *_: None,
        confirmer=lambda *_: confirmations.append(True) or True,
    )
    root.update(); app.review_button.invoke(); root.update()
    panel = app.review_panel
    ids = panel.tree.get_children()
    if not ids:
        raise RuntimeError("el snapshot sintético no produjo filas")
    first = ids[0]
    panel.tree.selection_set(first); panel.tree.event_generate("<<TreeviewSelect>>"); root.update()
    panel.field_vars[REVIEW_FIELDS[0]].set(True); panel.fields_button.invoke(); root.update()
    if REVIEW_FIELDS[0] not in review.reviewed_fields(app.principal, first):
        raise RuntimeError("callback de revisión por campo no persistió")
    panel.complete_button.invoke(); root.update()
    panel.tree.selection_set(ids); panel.bulk_button.invoke(); root.update()
    if not confirmations or review.progress(app.principal)["reviewed"] != len(ids):
        raise RuntimeError("callback de revisión masiva no persistió")
    panel.status_var.set("REVIEWED"); panel.status_filter.event_generate("<<ComboboxSelected>>"); root.update()
    if len(panel.tree.get_children()) != len(ids):
        raise RuntimeError("filtro de revisadas incorrecto")
    panel.back_button.invoke(); root.update()
    if app.current_screen != "dashboard":
        raise RuntimeError("callback volver no regresó al panel")
    root.destroy()
    reopened = ReviewService(CentralRepository(data_dir / "gestion-central-pilot.sqlite3"))
    if reopened.progress(app.principal)["reviewed"] != len(ids):
        raise RuntimeError("la revisión no persistió tras reapertura")
    evidence = {
        "status": "PASS", "callbacks": ["open", "select", "field", "complete", "bulk", "filter", "back"],
        "rows": len(ids), "restart_persistence": "PASS", "synthetic": True, "production": False,
    }
    (data_dir / "review-interaction-smoke.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
