import tkinter as tk

import pytest

from modulos.gestion_central.models import Principal, Role
from modulos.gestion_central.real_sync import REVIEW_FIELDS, ReviewService
from modulos.gestion_central.repository import CentralRepository
from modulos.gestion_central.service import CentralManagementService
from modulos.gestion_central.ui import CentralPilotWindow
from tests.gestion_central.test_real_sync_review import make_snapshot


@pytest.fixture
def review_app(tmp_path, tk_session):
    central = CentralManagementService(CentralRepository(tmp_path / "central.sqlite3"))
    central.bootstrap_synthetic_pilot()
    review = ReviewService(central.repository)
    review.import_snapshot(
        Principal("admin", Role.ADMIN_CENTRAL), make_snapshot(tmp_path / "source.sqlite3"),
        organization="BC", branch="Pilar",
    )
    root = tk.Toplevel(tk_session); root.withdraw()
    confirmations = []
    app = CentralPilotWindow(
        central, root=root, notifier=lambda *_: None,
        confirmer=lambda title, message: confirmations.append((title, message)) or True,
    )
    root.update()
    yield app, review, confirmations
    if root.winfo_exists(): root.destroy()


def select(panel, *ids):
    panel.tree.selection_set(ids)
    panel.tree.event_generate("<<TreeviewSelect>>")
    panel.update_idletasks()


def test_review_entry_selection_fields_navigation_and_back_callbacks(review_app):
    app, service, _ = review_app
    app.review_button.invoke(); app.root.update()
    panel = app.review_panel
    ids = panel.tree.get_children()
    assert len(ids) == 3
    select(panel, ids[0])
    assert panel.current_identity == ids[0]
    panel.field_vars[REVIEW_FIELDS[0]].set(True)
    panel.fields_button.invoke(); app.root.update()
    assert REVIEW_FIELDS[0] in service.reviewed_fields(app.principal, ids[0])
    panel.next_button.invoke(); app.root.update()
    assert panel.current_identity == ids[1]
    panel.previous_button.invoke(); app.root.update()
    assert panel.current_identity == ids[0]
    panel.back_button.invoke(); app.root.update()
    assert app.current_screen == "dashboard"


def test_individual_bulk_filter_and_restart_persistence_callbacks(review_app):
    app, service, confirmations = review_app
    app.review_button.invoke(); app.root.update()
    panel = app.review_panel
    ids = panel.tree.get_children()
    select(panel, ids[0])
    panel.complete_button.invoke(); app.root.update()
    rows = {row["identity"]: row for row in service.list_sales(app.principal)}
    assert rows[ids[0]]["review_status"] == "REVIEWED"
    select(panel, *ids)
    panel.bulk_button.invoke(); app.root.update()
    assert confirmations and "3 filas" in confirmations[-1][1]
    assert service.progress(app.principal)["reviewed"] == 3
    panel.status_var.set("REVIEWED"); panel.status_filter.event_generate("<<ComboboxSelected>>"); app.root.update()
    assert len(panel.tree.get_children()) == 3
    database = service.repository.database_path
    reopened = ReviewService(CentralRepository(database))
    assert reopened.progress(app.principal)["reviewed"] == 3


def test_full_hd_review_layout_keeps_controls_visible(review_app):
    app, _, _ = review_app
    app.root.deiconify(); app.root.geometry("1920x1080+0+0"); app.review_button.invoke(); app.root.update()
    panel = app.review_panel
    assert panel.back_button.winfo_ismapped()
    assert panel.tree.winfo_ismapped()
    assert panel.bulk_button.winfo_ismapped()
    assert panel.complete_button.winfo_ismapped()
    assert panel.winfo_height() <= app.body.winfo_height()
    assert panel.tree.tag_configure("REVIEWED")["background"]
    app.root.withdraw()


def test_dialog_keyboard_mark_continue_cancel_and_error_feedback(review_app, monkeypatch):
    app, service, confirmations = review_app
    app.review_button.invoke(); app.root.update(); panel = app.review_panel
    ids = panel.tree.get_children(); select(panel, ids[0])
    answers = iter(("Observación sintética", "Corrección sintética", "Alerta sintética"))
    monkeypatch.setattr("modulos.gestion_central.review_ui.simpledialog.askstring", lambda *_a, **_k: next(answers))
    panel.note_button.invoke(); panel.correction_button.invoke(); panel.alert_button.invoke(); app.root.update()
    assert len(service.notes(app.principal, ids[0])) == 1
    assert "BRANCH_ALERT_QUEUED" in {event["action"] for event in service.events(app.principal, ids[0])}
    app.root.deiconify(); select(panel, ids[1]); panel.tree.focus_set(); app.root.update()
    assert panel.tree.bind("<Return>")
    panel.tree.event_generate("<KeyPress-Return>"); app.root.update(); app.root.withdraw()
    rows = {row["identity"]: row for row in service.list_sales(app.principal)}
    assert rows[ids[1]]["review_status"] == "REVIEWED"
    select(panel, ids[0]); panel.mark_continue_button.invoke(); app.root.update()
    assert panel.current_identity != ids[0]
    panel.confirmer = lambda *_: False
    select(panel, ids[-1]); before = service.progress(app.principal)["reviewed"]
    panel.bulk_button.invoke(); app.root.update()
    assert service.progress(app.principal)["reviewed"] == before
    monkeypatch.setattr(panel.service, "mark_complete", lambda *_: (_ for _ in ()).throw(RuntimeError("synthetic")))
    panel.complete_button.invoke(); app.root.update()
    assert panel.feedback.cget("text").startswith("No se pudo")
    current = panel.current_identity
    panel.mark_continue_button.invoke(); app.root.update()
    assert panel.current_identity == current
    assert panel.feedback.cget("text").startswith("No se pudo")
