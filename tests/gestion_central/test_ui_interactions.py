from datetime import timedelta
import tkinter as tk

import pytest

from modulos.gestion_central.models import CashSnapshot, Principal, Role, Unit, utc_now
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import CentralManagementService
from modulos.gestion_central.ui import CentralPilotWindow, build_ui_logger


@pytest.fixture
def interactive_app(tmp_path, tk_session):
    service = CentralManagementService(CentralRepository(tmp_path / "central.sqlite3"))
    service.bootstrap_synthetic_pilot()
    service.ingest_snapshot(Principal("system", Role.ADMIN_CENTRAL), CashSnapshot(
        event_id="interactive-alert", unit=Unit.OPTICA_ASUNCION,
        business_date="2099-01-15", status="OPEN", opening_cash=500_000,
        income=800_000, cash=500_000, card_check=300_000, expenses=50_000,
        withdrawals=25_000, expected_cash=925_000, counted_cash=900_000,
        entry_count=5, source_updated_at=utc_now() + timedelta(seconds=2),
    ))
    root = tk.Toplevel(tk_session); root.withdraw()
    notices = []
    app = CentralPilotWindow(service, root=root, notifier=lambda title, text: notices.append((title, text)))
    root.update()
    yield app, service, notices
    try:
        if root.winfo_exists(): root.destroy()
    except tk.TclError:
        pass


def test_each_card_callback_opens_correct_detail_and_back(interactive_app):
    app, _, _ = interactive_app
    for unit in Unit:
        assert unit in app.card_buttons
        app.card_buttons[unit].invoke(); app.root.update()
        assert app.current_screen == "detail"
        assert app.selected_unit == unit
        assert unit.label in app.status_var.get()
        app.back_button.invoke(); app.root.update()
        assert app.current_screen == "dashboard"
        assert len(app.card_buttons) == 4


def test_detail_uses_horizontal_full_hd_layout_without_primary_vertical_scroll(interactive_app):
    app, _, _ = interactive_app
    app.root.deiconify(); app.root.geometry("1920x1080+0+0"); app.root.update()
    app.card_buttons[Unit.OPTICA_ASUNCION].invoke(); app.root.update()
    assert len(app.detail_kpis) == 7
    assert app.economics_tree["columns"] == ("concept", "amount", "reference", "status")
    assert app.detail_alerts.winfo_ismapped()
    assert app.economics_tree.winfo_ismapped()
    assert app.back_button.winfo_ismapped()
    assert app.detail_refresh_button.winfo_ismapped()
    assert max(child.winfo_y() + child.winfo_height() for child in app.body.winfo_children()) <= app.body.winfo_height()
    app.detail_refresh_button.invoke(); app.root.update()
    assert app.status_var.get().startswith("Detalle actualizado ")
    app.root.withdraw()


def test_refresh_and_filters_have_visible_feedback(interactive_app):
    app, _, _ = interactive_app
    app.refresh_button.invoke(); app.root.update()
    assert app.status_var.get().startswith("Actualizado ")
    app.filter_var.set("Con alertas"); app.filter_box.event_generate("<<ComboboxSelected>>"); app.root.update()
    assert "Filtro «Con alertas»" in app.status_var.get()
    assert set(app.card_buttons) == {Unit.OPTICA_ASUNCION}
    app.filter_var.set("Todas"); app.apply_filter()
    assert len(app.card_buttons) == 4


def test_alert_selection_acknowledgement_and_restart_persistence(interactive_app, tk_session):
    app, service, _ = interactive_app
    alert_id = app.alerts.get_children()[0]
    app.alerts.selection_set(alert_id); app.alerts.event_generate("<<TreeviewSelect>>"); app.root.update()
    assert "Alerta seleccionada" in app.status_var.get()
    assert app.ack_button.invoke()
    app.root.update()
    assert alert_id not in app.alerts.get_children()
    assert "Alerta reconocida" in app.status_var.get()
    assert any(row["action"] == "ALERT_ACK" and row["target"] == alert_id for row in service.repository.audit_log())
    app.root.destroy()
    # Con master explícito: sin él colgaba del `_default_root` global, que es
    # justo la variable cuyo valor depende del orden de los módulos.
    reopened_root = tk.Toplevel(tk_session); reopened_root.withdraw()
    reopened = CentralPilotWindow(service, root=reopened_root, notifier=lambda *_: None)
    reopened_root.update()
    assert alert_id not in reopened.alerts.get_children()
    assert not service.repository.alerts()
    reopened_root.destroy()


def test_silent_clicks_are_replaced_by_message_and_safe_log(interactive_app, tmp_path):
    app, _, notices = interactive_app
    assert app.acknowledge() is False
    assert notices[-1][1] == "Seleccione una alerta activa."
    logger = build_ui_logger(tmp_path)
    app.logger = logger
    app._guard(lambda: (_ for _ in ()).throw(RuntimeError("synthetic UI failure")), "acción sintética")
    for handler in logger.handlers: handler.flush()
    log = (tmp_path / "Logs" / "ui-errors.log").read_text(encoding="utf-8")
    assert "acción sintética" in log
    assert "password" not in log.lower()
