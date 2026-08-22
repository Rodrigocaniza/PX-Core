from __future__ import annotations

from pathlib import Path
import tkinter as tk

import pytest

from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from modulos.gestion_central.models import Principal, Role
from modulos.gestion_central.pending_ui import ALL_BRANCHES, PendingPanel, merge_log
from modulos.gestion_central.real_sync import ReviewService
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import AccessDenied


ROOT = Path(__file__).resolve().parents[2]
ADMIN = Principal("sol", Role.ADMIN_CENTRAL)
AUDITOR = Principal("auditora", Role.AUDITOR)
LOCAL = Principal("sucursal", Role.OPERADOR_LOCAL)


def make_snapshot(path: Path, *, sales=3):
    repo = SQLiteCashDayRepository(path)
    with repo._connection() as con:
        con.execute("INSERT INTO cash_days(id,business_date,unit,opening_cash,status,opened_at,closed_at,version)"
                    " VALUES('day','2099-02-20','PC',500000,'CLOSED','2099-02-20T08:00:00-03:00','2099-02-20T18:00:00-03:00',1)")
        for index in range(sales):
            con.execute("""INSERT INTO cash_entries(id,cash_day_id,description,envelope,total,cash,card_check,agreement_amount,balance_text,customer_document,customer_phone,saleswoman,delivery_date,observations,performed_by,created_at,updated_at,revision)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (f"sale-{index}", "day", f"Cliente Sintético {index + 1}", f"S-{index + 1:03d}",
                         1000000 + index, 500000, 300000, 200000, "0", f"DOC-{index}", f"09810000{index}",
                         "Vendedora Piloto", "2099-02-25", "Observación sintética", "operador.piloto",
                         "2099-02-20T10:00:00-03:00", "2099-02-20T10:00:00-03:00", 1))
            con.execute("INSERT INTO sale_items(id,cash_entry_id,position,description,code,item_type,frame_price,lens_price,laboratory,prescription_doctor)"
                        " VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (f"item-{index}", f"sale-{index}", 0, "Armazón sintético", f"COD-{index}",
                         "ARMAZON", 400000, 600000, "Laboratorio Piloto", "Dra. Prueba"))
        con.commit()
    repo.close()
    return path


@pytest.fixture
def queued(tmp_path):
    """Dos correcciones y una alerta encoladas sobre ventas sintéticas."""
    snapshot = make_snapshot(tmp_path / "snapshot.sqlite3", sales=3)
    service = ReviewService(CentralRepository(tmp_path / "central.sqlite3"))
    service.import_snapshot(ADMIN, snapshot, branch="Pilar")
    identities = [sale["identity"] for sale in service.list_sales(ADMIN)]
    service.add_note(ADMIN, identities[0], "Verificar el importe con la vendedora")
    service.require_correction(ADMIN, identities[0], "Total no coincide con el sobre", field_name="total")
    service.require_correction(ADMIN, identities[1], "Falta la receta escaneada")
    service.create_branch_alert(ADMIN, identities[0], "Llamar al cliente antes de entregar")
    return service, identities


# -- servicio ----------------------------------------------------------


def test_pending_alerts_lists_the_queue_without_dispatching_anything(queued):
    service, identities = queued
    alerts = service.pending_alerts(ADMIN)
    assert [alert["identity"] for alert in alerts] == [identities[0]]
    assert alerts[0]["status"] == "PENDING"
    assert alerts[0]["message"] == "Llamar al cliente antes de entregar"
    assert alerts[0]["branch"] == "Pilar"


def test_pending_alerts_filter_by_branch_and_require_read_permission(queued):
    service, _identities = queued
    assert len(service.pending_alerts(AUDITOR, branch="Pilar")) == 1
    assert service.pending_alerts(ADMIN, branch="Asuncion") == []
    with pytest.raises(AccessDenied):
        service.pending_alerts(LOCAL)


def test_pending_alerts_stay_idempotent_when_the_same_alert_is_queued_again(queued):
    service, identities = queued
    service.create_branch_alert(ADMIN, identities[0], "Llamar al cliente antes de entregar")
    assert len(service.pending_alerts(ADMIN)) == 1


def test_merge_log_orders_notes_and_events_in_one_timeline(queued):
    service, identities = queued
    entries = merge_log(service.notes(ADMIN, identities[0]), service.events(ADMIN, identities[0]))
    assert [entry["recorded_at"] for entry in entries] == sorted(entry["recorded_at"] for entry in entries)
    kinds = {entry["kind"] for entry in entries}
    assert kinds == {"Observación", "Evento"}
    note = next(entry for entry in entries if entry["kind"] == "Observación")
    assert note["detail"] == "Verificar el importe con la vendedora"
    reopen = next(entry for entry in entries if "REOPEN_CORRECTION" in entry["detail"])
    assert "REQUIRES_CORRECTION" in reopen["detail"]
    assert "Total no coincide con el sobre" in reopen["detail"]
    assert reopen["field"] == "total"


def test_pending_panel_source_queues_nothing_and_sends_nothing():
    source = (ROOT / "modulos" / "gestion_central" / "pending_ui.py").read_text(encoding="utf-8")
    for forbidden in ("create_branch_alert", "require_correction", "mark_fields", "mark_complete",
                      "mark_many", "add_note", "smtp", "requests", "urllib", "telegram"):
        assert forbidden not in source, f"la pantalla no puede usar {forbidden}"


# -- pantalla ----------------------------------------------------------


@pytest.fixture(scope="module")
def tk_session():
    root = tk.Tk(); root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def panel(queued, tk_session):
    service, identities = queued
    root = tk.Toplevel(tk_session); root.withdraw()
    back = []
    widget = PendingPanel(root, service, ADMIN, back=lambda: back.append(True), notifier=lambda *_: None)
    widget.pack(fill="both", expand=True); root.update()
    yield widget, root, back, identities
    try:
        if root.winfo_exists(): root.destroy()
    except tk.TclError:
        pass


def test_panel_lists_both_queues_with_context_and_kpis(panel):
    widget, _root, _back, _identities = panel
    assert len(widget.corrections_tree.get_children()) == 2
    assert len(widget.alerts_tree.get_children()) == 1
    assert widget.kpis["corrections"].cget("text") == "2"
    assert widget.kpis["alerts"].cget("text") == "1"
    assert widget.kpis["rows"].cget("text") == "2"
    assert widget.kpis["branches"].cget("text") == "1"
    assert "Más antiguo:" in widget.oldest_label.cget("text")
    first = widget.corrections_tree.item(widget.corrections_tree.get_children()[0], "values")
    assert first[1] == "Pilar" and first[3] == "S-001" and first[4] == "total"
    second = widget.corrections_tree.item(widget.corrections_tree.get_children()[1], "values")
    assert second[4] == "Fila completa"


def test_panel_shows_the_log_of_the_selected_pending_row(panel):
    widget, root, _back, _identities = panel
    rows = widget.corrections_tree.get_children()
    widget.corrections_tree.selection_set(rows[0]); widget.corrections_tree.event_generate("<<TreeviewSelect>>"); root.update()
    assert "S-001" in widget.log_title.cget("text")
    details = [widget.log_tree.item(item, "values")[-1] for item in widget.log_tree.get_children()]
    assert any("Verificar el importe" in detail for detail in details)
    assert any("REOPEN_CORRECTION" in detail for detail in details)
    assert any("BRANCH_ALERT_QUEUED" in detail for detail in details)


def test_panel_selecting_an_alert_reuses_the_same_log(panel):
    widget, root, _back, identities = panel
    alert = widget.alerts_tree.get_children()[0]
    widget.alerts_tree.selection_set(alert); widget.alerts_tree.event_generate("<<TreeviewSelect>>"); root.update()
    assert widget.current_identity == identities[0]
    assert widget.log_tree.get_children() != ()


def test_panel_keeps_a_stable_order_when_requests_share_the_same_second(panel):
    widget, root, _back, _identities = panel
    def snapshot():
        return [widget.corrections_tree.item(item, "values") for item in widget.corrections_tree.get_children()]
    first = snapshot()
    assert [row[3] for row in first] == ["S-001", "S-002"]
    for _ in range(3):
        widget.reload_button.invoke(); root.update()
        assert snapshot() == first


def test_panel_filters_by_branch_and_returns_to_the_dashboard(panel):
    widget, root, back, _identities = panel
    assert ALL_BRANCHES in widget.branch_filter.cget("values")
    assert "Pilar" in widget.branch_filter.cget("values")
    widget.branch_var.set("Pilar"); widget.branch_filter.event_generate("<<ComboboxSelected>>"); root.update()
    assert len(widget.corrections_tree.get_children()) == 2
    widget.branch_var.set(ALL_BRANCHES); widget.reload_button.invoke(); root.update()
    assert len(widget.corrections_tree.get_children()) == 2
    widget.back_button.invoke()
    assert back == [True]


def test_panel_with_an_empty_queue_reports_no_pending_work(tmp_path, tk_session):
    service = ReviewService(CentralRepository(tmp_path / "vacia.sqlite3"))
    root = tk.Toplevel(tk_session); root.withdraw()
    widget = PendingPanel(root, service, ADMIN, back=lambda: None, notifier=lambda *_: None)
    widget.pack(fill="both", expand=True); root.update()
    assert widget.corrections_tree.get_children() == ()
    assert widget.alerts_tree.get_children() == ()
    assert widget.kpis["corrections"].cget("text") == "0"
    assert widget.oldest_label.cget("text") == "Sin pendientes"
    root.destroy()


def test_pilot_window_opens_and_leaves_the_pending_screen(tmp_path, tk_session):
    from modulos.gestion_central.service import CentralManagementService
    from modulos.gestion_central.ui import CentralPilotWindow

    snapshot = make_snapshot(tmp_path / "snapshot.sqlite3", sales=1)
    service = CentralManagementService(CentralRepository(tmp_path / "central.sqlite3"))
    service.bootstrap_synthetic_pilot()
    review = ReviewService(service.repository)
    review.import_snapshot(ADMIN, snapshot, branch="Pilar")
    identity = review.list_sales(ADMIN)[0]["identity"]
    review.require_correction(ADMIN, identity, "Revisar el saldo declarado")

    root = tk.Toplevel(tk_session); root.withdraw()
    app = CentralPilotWindow(service, root=root, notifier=lambda *_: None)
    root.update()
    app.pending_button.invoke(); root.update()
    assert app.current_screen == "pending"
    assert len(app.pending_panel.corrections_tree.get_children()) == 1
    app.pending_panel.back_button.invoke(); root.update()
    assert app.current_screen == "dashboard"
    root.destroy()
