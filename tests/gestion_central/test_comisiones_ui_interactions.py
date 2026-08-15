import tkinter as tk

import pytest

from bc_gestion_central import build_service
from modulos.gestion_central.comisiones import CommissionSaleInput, CommissionService
from modulos.gestion_central.ui import CentralPilotWindow


@pytest.fixture(scope="module")
def root():
    value = tk.Tk(); value.withdraw(); yield value; value.destroy()


@pytest.fixture
def app(tmp_path, root):
    core = build_service(tmp_path); core.bootstrap_synthetic_pilot()
    sol = core.authenticate("sol.piloto", "Piloto-Temporal-2026")
    commissions = CommissionService(core)
    pending, _ = commissions.register_sale(sol, CommissionSaleInput(
        "Óptica Asunción", "ui-pendiente", "Vendedora UI", "2099-04-10", "COMUN", 400_000, 200_000, "S-01"))
    settled, _ = commissions.register_sale(sol, CommissionSaleInput(
        "Óptica Asunción", "ui-cancelada", "Vendedora UI", "2099-04-11", "COMUN", 300_000, 300_000, "S-02"))
    convenio, _ = commissions.register_sale(sol, CommissionSaleInput(
        "Óptica Pilar", "ui-convenio", "Vendedora Dos", "2099-04-12", "CONVENIO", 500_000, envelope="S-03"))
    commissions.recalculate(sol)
    window = CentralPilotWindow(core, root=root, notifier=lambda *_: None)
    root.update()
    yield window, commissions, sol, {"pending": pending, "settled": settled, "convenio": convenio}
    window.content.destroy()


def entry_of(panel, sale_id):
    return next(row["id"] for row in panel.report["entries"] if row["sale_id"] == sale_id)


def test_navigation_filters_and_state_reasons(app, root):
    window, _, _, ids = app
    window.commissions_button.invoke(); root.update()
    panel = window.commissions_panel
    assert window.current_screen == "commissions"
    assert panel.period_var.get() == "2099-04" and len(panel.tree.get_children()) == 3
    assert panel.kpis["commissionable_base"].cget("text") == "775.000 Gs."
    assert panel.kpis["agreements"].cget("text") == "1"

    panel.tree.selection_set(entry_of(panel, ids["pending"])); panel.tree.event_generate("<<TreeviewSelect>>")
    root.update()
    assert "saldo pendiente" in panel.reason.cget("text")
    panel.tree.selection_set(entry_of(panel, ids["convenio"])); panel.tree.event_generate("<<TreeviewSelect>>")
    root.update()
    assert "Convenio" in panel.reason.cget("text")
    amounts = [child.winfo_children()[1].cget("text") for child in panel.breakdown.winfo_children()]
    assert amounts == ["500.000 Gs.", "25.000 Gs.", "475.000 Gs."]

    panel.branch_var.set("Óptica Pilar"); panel.branch_box.event_generate("<<ComboboxSelected>>"); root.update()
    assert len(panel.tree.get_children()) == 1
    panel.branch_var.set("TODOS"); panel.status_var.set("PENDIENTE_SALDO")
    panel.status_box.event_generate("<<ComboboxSelected>>"); root.update()
    assert len(panel.tree.get_children()) == 1
    panel.status_var.set("TODOS"); panel.period_var.set("2099-11"); panel.apply_button.invoke(); root.update()
    assert not panel.tree.get_children()
    panel.period_var.set("2099-04"); panel.apply_button.invoke(); root.update()
    panel.back(); root.update()
    assert window.current_screen == "dashboard"


def test_approval_flow_blocks_payment_without_approval(app, root):
    window, service, sol, ids = app
    window.show_commissions(); root.update()
    panel = window.commissions_panel
    answers = []
    panel.asker = lambda _title, _prompt: answers.pop(0)
    panel.notifier = lambda *args: answers.append(args)
    panel.tree.selection_set(entry_of(panel, ids["settled"])); panel.tree.event_generate("<<TreeviewSelect>>")
    root.update()
    entry_id = panel.current

    answers[:] = ["2099-05-05", "TRANSF-UI"]
    assert panel.mark_paid() is False
    assert service.get_entry(sol, entry_id)["status"] == "CALCULADA"

    assert panel.review()
    answers[:] = ["Sol"]
    assert panel.approve()
    answers[:] = ["2099-05-05", "TRANSF-UI"]
    assert panel.mark_paid()
    assert service.get_entry(sol, entry_id)["status"] == "PAGADA"
    assert panel.history.get_children()
    states = [panel.history.item(item, "values")[2] for item in panel.history.get_children()]
    assert states == ["ELEGIBLE", "CALCULADA", "REVISADA", "APROBADA", "PAGADA"]


def test_observe_revert_recalculate_and_export(app, root, tmp_path):
    window, service, sol, ids = app
    window.show_commissions(); root.update()
    panel = window.commissions_panel
    answers = []
    panel.asker = lambda _title, _prompt: answers.pop(0)
    panel.tree.selection_set(entry_of(panel, ids["convenio"])); panel.tree.event_generate("<<TreeviewSelect>>")
    root.update()
    entry_id = panel.current

    answers[:] = ["diferencia con la planilla"]
    assert panel.observe()
    assert service.get_entry(sol, entry_id)["status"] == "OBSERVADA"
    assert "OBSERVADA" in panel.reason.cget("text")

    answers[:] = ["corrección definitiva"]
    assert panel.revert()
    assert service.get_entry(sol, entry_id)["status"] == "REVERTIDA"

    assert panel.recalculate()["changed"] == 0
    target = panel.export()
    assert target.exists()
    assert '"contract_version": 1' in target.read_text(encoding="utf-8")
    assert "pendiente de aprobación" in panel.feedback.cget("text") or target.name.endswith(".local.json")


def test_full_hd_layout_keeps_every_control_visible(app, root):
    window, _, _, ids = app
    window.show_commissions(); root.deiconify(); root.geometry("1920x1080"); root.update()
    panel = window.commissions_panel
    panel.tree.selection_set(entry_of(panel, ids["convenio"])); panel.tree.event_generate("<<TreeviewSelect>>")
    root.update()
    assert panel.tree.winfo_width() >= 900 and panel.summary_tree.winfo_viewable()
    for button in (panel.review_button, panel.approve_button, panel.paid_button,
                   panel.observe_button, panel.revert_button, panel.recalculate_button, panel.export_button):
        assert button.winfo_viewable() and button.winfo_width() > 1
    assert panel.history.winfo_viewable() and panel.breakdown.winfo_viewable()
    assert panel.winfo_height() <= 1080
    # Ninguna columna monetaria puede quedar recortada fuera del ancho visible.
    for tree in (panel.tree, panel.summary_tree):
        columns = sum(tree.column(key, "width") for key in tree.cget("columns"))
        assert columns <= tree.winfo_width(), f"columnas recortadas: {columns} > {tree.winfo_width()}"
    assert panel.kpis["partial_payments_amount"].cget("text").endswith("Gs.")
