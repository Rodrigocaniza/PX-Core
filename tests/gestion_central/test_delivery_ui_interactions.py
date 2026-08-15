import tkinter as tk

import pytest

from bc_gestion_central import build_service
from modulos.gestion_central.delivery import DeliveryService
from modulos.gestion_central.models import Unit
from modulos.gestion_central.ui import CentralPilotWindow


@pytest.fixture(scope="module")
def root():
    value = tk.Tk(); value.withdraw(); yield value; value.destroy()


@pytest.fixture
def app(tmp_path, root):
    core = build_service(tmp_path); core.bootstrap_synthetic_pilot()
    sol = core.authenticate("sol.piloto", "Piloto-Temporal-2026")
    delivery = DeliveryService(core)
    delivery.queue(sol, Unit.OPTICA_ASUNCION, "Confirmar arqueo sintético", "CAJA-01")
    delivery.queue(sol, Unit.OPTICA_PILAR, "Equipo desconectado sintético", "OFFLINE-01")
    window = CentralPilotWindow(core, root=root, notifier=lambda *_: None)
    root.update()
    yield window, delivery
    window.content.destroy()


def test_messages_navigation_processing_filters_and_back(app, root):
    window, delivery = app
    window.messages_button.invoke(); root.update(); panel = window.delivery_panel
    assert window.current_screen == "messages" and len(panel.tree.get_children()) == 2
    first = panel.tree.get_children()[0]; panel.tree.selection_set(first); panel.tree.event_generate("<<TreeviewSelect>>"); root.update()
    assert "Idempotencia:" in panel.detail.get("1.0", "end")
    panel.process_button.invoke(); root.update()
    assert {row["state"] for row in delivery.list_messages(window.principal)} == {"CONFIRMADO", "REINTENTO"}
    panel.state_var.set("CONFIRMADO"); panel.reload(); root.update(); assert len(panel.tree.get_children()) == 1
    panel.back(); root.update(); assert window.current_screen == "dashboard"


def test_delivery_panel_full_hd_contract(app, root):
    window, _ = app; window.show_messages(); root.deiconify(); root.geometry("1920x1080"); root.update()
    panel = window.delivery_panel
    assert panel.tree.winfo_width() >= 1000
    assert panel.process_button.winfo_viewable() and panel.retry_button.winfo_viewable() and panel.cancel_button.winfo_viewable()
