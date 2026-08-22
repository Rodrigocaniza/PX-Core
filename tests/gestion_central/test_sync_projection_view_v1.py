from __future__ import annotations

from pathlib import Path
import sqlite3
import tkinter as tk

import pytest

from modulos.bc_sync.model import SyncEvent
from modulos.bc_sync.security import (
    AuthenticatedMessage, SecurityAuthorizationError, SecurityIdentity,
)
from modulos.gestion_central.models import Principal, Role, Unit
from modulos.gestion_central.service import AccessDenied
from modulos.gestion_central.sync_projection_view import SyncProjectionView
from modulos.gestion_central.sync_receiver import CentralSyncInbox


ROOT = Path(__file__).resolve().parents[2]
SUPERVISOR = Principal("sol", Role.SUPERVISOR)
AUDITOR = Principal("auditor", Role.AUDITOR)
PILAR_LOCAL = Principal("pilar", Role.OPERADOR_LOCAL, Unit.OPTICA_PILAR)


class StubAuth:
    """Sólo tests: BC Seguridad real verifica la credencial en el despliegue."""

    def __init__(self):
        self.rejected = set()

    def verify_event(self, message: AuthenticatedMessage) -> SecurityIdentity:
        installation = str(message.body.get("installation_id", ""))
        if installation in self.rejected:
            raise SecurityAuthorizationError("credencial no verificada")
        return SecurityIdentity(installation, str(message.body.get("branch_id", "")).upper(), "lic-test", "1")


def message(*, installation, branch, event_type, payload, key, occurred_at):
    event = SyncEvent.create(installation_id=installation, branch_id=branch, event_type=event_type,
                             payload=payload, idempotency_key=key, occurred_at=occurred_at)
    return AuthenticatedMessage(event.wire_dict(), {"installation_id": installation})


@pytest.fixture
def populated(tmp_path):
    database = tmp_path / "central-sync.sqlite3"
    auth = StubAuth()
    inbox = CentralSyncInbox(database, auth)
    venta = message(installation="inst-asu", branch="ASUNCION", event_type="VENTA",
                    payload={"sale_id": "V-1", "envelope": "SO-9", "customer_name": "Ana Rojas",
                             "customer_document": "1234567"},
                    key="k-venta", occurred_at="2099-01-10T10:00:00+00:00")
    sobre = message(installation="inst-pil", branch="PILAR", event_type="SOBRE",
                    payload={"sale_id": "V-2", "envelope": "SO-10", "customer_name": "Beto Díaz",
                             "customer_document": "7654321"},
                    key="k-sobre", occurred_at="2099-01-10T11:00:00+00:00")
    factura = message(installation="inst-asu", branch="ASUNCION", event_type="FACTURACION_ESTADO",
                      payload={"sale_id": "V-1", "state": "CARGADA", "invoice_number": "001-002-3"},
                      key="k-factura", occurred_at="2099-01-10T12:00:00+00:00")
    for item in (venta, sobre, factura):
        assert inbox.receive(item) is True
    assert inbox.receive(venta) is False  # retry legítimo: duplicado sin segundo efecto
    auth.rejected.add("inst-falso")
    with pytest.raises(SecurityAuthorizationError):
        inbox.receive(message(installation="inst-falso", branch="PILAR", event_type="VENTA",
                              payload={"sale_id": "V-3"}, key="k-falso",
                              occurred_at="2099-01-10T13:00:00+00:00"))
    return SyncProjectionView(database)


def test_rows_keep_receiver_order_and_translate_category_and_branch(populated):
    rows = populated.rows(SUPERVISOR)
    assert [row["occurred_at"] for row in rows] == [
        "2099-01-10T10:00:00+00:00", "2099-01-10T11:00:00+00:00", "2099-01-10T12:00:00+00:00"]
    assert [row["category"] for row in rows] == ["VENTA", "SOBRE", "FACTUFACIL"]
    assert [row["category_label"] for row in rows] == ["Venta", "Sobre", "FactuFácil"]
    assert rows[0]["unit"] is Unit.OPTICA_ASUNCION and rows[0]["unit_label"] == "Óptica Asunción"
    assert rows[1]["unit_label"] == "Óptica Pilar"
    assert rows[0]["payload"]["customer_name"] == "Ana Rojas"
    assert {row["sync_state"] for row in rows} == {"RECEIVED"}


def test_filters_by_category_unit_state_and_free_text(populated):
    assert len(populated.rows(SUPERVISOR, category="VENTA")) == 1
    assert len(populated.rows(SUPERVISOR, unit=Unit.OPTICA_PILAR)) == 1
    assert [row["invoice_number"] for row in populated.factufacil(SUPERVISOR, state="CARGADA")] == ["001-002-3"]
    assert populated.factufacil(SUPERVISOR, state="PENDIENTE") == ()
    assert [row["sale_id"] for row in populated.rows(SUPERVISOR, text="beto")] == ["V-2"]
    assert [row["envelope"] for row in populated.rows(SUPERVISOR, text="SO-9")] == ["SO-9"]


def test_summary_counts_categories_units_and_receiver_outcomes(populated):
    summary = populated.summary(SUPERVISOR)
    assert summary["total"] == 3
    assert summary["categories"]["VENTA"] == 1 and summary["categories"]["FACTUFACIL"] == 1
    assert summary["categories"]["RECETA"] == 0
    assert summary["units"] == {"Óptica Asunción": 2, "Óptica Pilar": 1}
    assert summary["last_occurred_at"] == "2099-01-10T12:00:00+00:00"
    assert summary["duplicated"] == 1 and summary["rejected"] == 1


def test_rejections_expose_sanitized_reason_and_require_audit_permission(populated):
    rejections = populated.rejections(AUDITOR)
    assert [row["outcome"] for row in rejections] == ["REJECTED", "DUPLICATE"]
    rejected = rejections[0]
    assert rejected["unit_label"] == "Óptica Pilar"
    assert "credencial no verificada" in rejected["reason"]
    assert "\n" not in rejected["reason"]
    with pytest.raises(AccessDenied):
        populated.rejections(PILAR_LOCAL)
    assert populated.summary(PILAR_LOCAL)["rejected"] == 0


def test_principal_bound_to_a_unit_only_sees_its_own_branch(populated):
    rows = populated.rows(PILAR_LOCAL)
    assert [row["unit_label"] for row in rows] == ["Óptica Pilar"]
    assert populated.summary(PILAR_LOCAL)["total"] == 1
    assert populated.rows(PILAR_LOCAL, unit=Unit.OPTICA_ASUNCION) == ()


def test_reading_requires_dashboard_permission(populated):
    class Nobody:
        role = Role.AUDITOR
        unit = None

        @staticmethod
        def allows(_permission, _unit=None):
            return False

    with pytest.raises(AccessDenied):
        populated.rows(Nobody())


def test_connection_refuses_every_write_attempt(populated):
    with populated.connection() as db:
        for statement in ("INSERT INTO central_sync_audit(audit_at,outcome) VALUES('x','y')",
                          "DELETE FROM central_sync_projection",
                          "UPDATE central_sync_projection SET sync_state='ALTERADO'"):
            with pytest.raises(sqlite3.OperationalError):
                db.execute(statement)


def test_missing_database_reads_as_empty_instead_of_failing(tmp_path):
    view = SyncProjectionView(tmp_path / "todavia-no-existe.sqlite3")
    assert view.rows(SUPERVISOR) == ()
    assert view.rejections(AUDITOR) == ()
    assert view.summary(SUPERVISOR) == {
        "total": 0, "categories": {"CLIENTE_HISTORIAL": 0, "VENTA": 0, "SOBRE": 0,
                                   "RECETA": 0, "FACTUFACIL": 0, "EVENTO": 0},
        "units": {}, "last_occurred_at": "", "rejected": 0, "duplicated": 0}
    assert not (tmp_path / "todavia-no-existe.sqlite3").exists()


def test_view_and_panel_sources_contain_no_write_statements():
    for name in ("sync_projection_view.py", "sync_projection_ui.py"):
        source = (ROOT / "modulos" / "gestion_central" / name).read_text(encoding="utf-8").upper()
        for statement in ("INSERT INTO", "UPDATE ", "DELETE FROM", "CREATE TABLE", "DROP "):
            assert statement not in source, f"{name} no puede escribir: {statement}"


# -- pantalla ----------------------------------------------------------


@pytest.fixture(scope="module")
def tk_session():
    root = tk.Tk(); root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def panel(populated, tk_session):
    from modulos.gestion_central.sync_projection_ui import ALL_UNITS, SyncProjectionPanel

    root = tk.Toplevel(tk_session); root.withdraw()
    back = []
    widget = SyncProjectionPanel(root, populated, SUPERVISOR, back=lambda: back.append(True),
                                 notifier=lambda *_: None)
    widget.pack(fill="both", expand=True); root.update()
    yield widget, root, back, ALL_UNITS
    try:
        if root.winfo_exists(): root.destroy()
    except tk.TclError:
        pass


def test_panel_lists_receptions_kpis_and_rejections(panel):
    widget, _root, _back, _all_units = panel
    assert len(widget.tree.get_children()) == 3
    assert widget.kpis["total"].cget("text") == "3"
    assert widget.kpis["VENTA"].cget("text") == "1"
    assert widget.kpis["rejected"].cget("text") == "1"
    assert widget.kpis["duplicated"].cget("text") == "1"
    assert "2099-01-10 12:00:00" in widget.last_label.cget("text")
    assert len(widget.rejections_tree.get_children()) == 2


def test_panel_filters_select_and_return_without_writing(panel):
    widget, root, back, all_units = panel
    widget.unit_var.set("Óptica Pilar"); widget.unit_filter.event_generate("<<ComboboxSelected>>"); root.update()
    assert len(widget.tree.get_children()) == 1
    widget.unit_var.set(all_units); widget.unit_filter.event_generate("<<ComboboxSelected>>"); root.update()
    widget.category_var.set("FactuFácil"); widget.category_filter.event_generate("<<ComboboxSelected>>"); root.update()
    rows = widget.tree.get_children()
    assert len(rows) == 1
    widget.tree.selection_set(rows[0]); widget.tree.event_generate("<<TreeviewSelect>>"); root.update()
    assert "FactuFácil" in widget.detail_label.cget("text")
    assert "invoice_number=001-002-3" in widget.detail_label.cget("text")
    widget.text_var.set("no-existe"); widget.reload_button.invoke(); root.update()
    assert widget.tree.get_children() == ()
    widget.back_button.invoke()
    assert back == [True]


def test_pilot_window_opens_and_leaves_the_reception_screen(populated, tmp_path, tk_session):
    from modulos.gestion_central.repository import CentralRepository
    from modulos.gestion_central.service import CentralManagementService
    from modulos.gestion_central.ui import CentralPilotWindow

    service = CentralManagementService(CentralRepository(tmp_path / "central.sqlite3"))
    service.bootstrap_synthetic_pilot()
    root = tk.Toplevel(tk_session); root.withdraw()
    app = CentralPilotWindow(service, root=root, notifier=lambda *_: None,
                             sync_database=populated.database)
    root.update()
    app.sync_button.invoke(); root.update()
    assert app.current_screen == "sync"
    assert len(app.sync_panel.tree.get_children()) == 3
    app.sync_panel.back_button.invoke(); root.update()
    assert app.current_screen == "dashboard"
    root.destroy()


def test_panel_hides_rejections_when_the_principal_cannot_audit(populated, tk_session):
    from modulos.gestion_central.sync_projection_ui import SyncProjectionPanel

    root = tk.Toplevel(tk_session); root.withdraw()
    widget = SyncProjectionPanel(root, populated, PILAR_LOCAL, back=lambda: None, notifier=lambda *_: None)
    widget.pack(fill="both", expand=True); root.update()
    assert len(widget.tree.get_children()) == 1
    assert widget.kpis["rejected"].cget("text") == "0"
    reasons = [widget.rejections_tree.item(item, "values")[-1] for item in widget.rejections_tree.get_children()]
    assert reasons == ["Sin permiso de auditoría"]
    root.destroy()
