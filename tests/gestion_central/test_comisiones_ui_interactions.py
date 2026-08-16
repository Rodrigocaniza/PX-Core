import tkinter as tk

import pytest

from bc_gestion_central import build_service
from modulos.gestion_central.comisiones import CommissionSaleInput, CommissionService
from modulos.gestion_central.comisiones_ui import ENTRY_COLUMNS
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
    # Total, descuento del convenio, base comisionable y comisión oficial del 1%.
    labels = [child.winfo_children()[0].cget("text") for child in panel.breakdown.winfo_children()]
    amounts = [child.winfo_children()[1].cget("text") for child in panel.breakdown.winfo_children()]
    assert amounts == ["500.000 Gs.", "25.000 Gs.", "475.000 Gs.", "4.750 Gs."]
    assert labels[-1] == "= Comisión oficial (1,00% de la base)"
    assert "1,00%" in panel.policy_note.cget("text")

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
    exported = target.read_text(encoding="utf-8")
    assert '"contract_version": 2' in exported
    assert '"code": "COMISION_GENERAL_1PCT"' in exported and '"rate_percent": "1.00"' in exported
    assert '"policy_version": 1' in exported and '"rounding": "HALF_UP"' in exported
    assert target.name.endswith(".local.json")


def test_the_screen_names_the_official_one_percent_policy(app, root):
    window, service, sol, ids = app
    window.show_commissions(); root.update()
    panel = window.commissions_panel
    header = panel.policy_label.cget("text")
    assert "Comisión oficial 1,00% de la base" in header
    assert "COMISION_GENERAL_1PCT v1" in header and "vigente desde 2026-08-01" in header
    assert "HALF_UP" in header
    assert panel.kpi_captions["commission_amount"].cget("text") == "COMISIÓN OFICIAL 1,00%"
    # Las columnas no llevan el porcentaje: una fila puede arrastrar un importe de una
    # política retirada, y encabezarla «Comisión 1,00%» lo declararía oficial sin serlo.
    assert panel.tree.heading("commission_amount", "text") == "Comisión"
    assert panel.summary_tree.heading("commission_amount", "text") == "Comisión"
    # Sin importes fuera de la política vigente, el aviso no ocupa lugar en pantalla.
    assert not panel.warning.winfo_ismapped()
    # Base y comisión oficial visibles en la fila, sin abrir el desglose.
    row = next(entry for entry in panel.report["entries"] if entry["sale_id"] == ids["settled"])
    values = panel.tree.item(row["id"], "values")
    columns = [key for key, *_ in ENTRY_COLUMNS]
    assert values[columns.index("commissionable_base")] == "300.000 Gs."
    assert values[columns.index("commission_amount")] == "3.000 Gs."
    assert panel.kpis["commission_amount"].cget("text") == "7.750 Gs."


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


def test_the_screen_never_calls_official_an_amount_from_a_retired_policy(app, root, tmp_path):
    """Bloqueante QA generación 2: los agregados rotulaban «1,00%» un importe al 7%."""
    import sqlite3

    window, service, sol, ids = app
    entry_id = next(row["id"] for row in service.list_entries(sol) if row["sale_id"] == ids["convenio"])
    with sqlite3.connect(service.repository.database_path) as con:
        # Liquidación legada ya pagada: conserva su importe y nunca se repara.
        con.execute("UPDATE commission_entries SET status='PAGADA',paid_at='2099-05-01',"
                    "payment_reference='TRANSF-LEGADA',rate_bp=700,commission_amount=33250,"
                    "policy_status='POLITICA_HISTORICA_PREVIA',policy_code=NULL,policy_version=NULL,"
                    "policy_effective_from=NULL,policy_scope=NULL WHERE id=?", (entry_id,))
        con.commit()
    window.show_commissions(); root.update()
    panel = window.commissions_panel
    panel.reload(); root.update()

    kpi = panel.report["kpi"]
    # 300.000 al 1% es lo único oficial del período; los 33.250 al 7% van aparte.
    assert kpi["commission_amount"] == 3_000
    assert kpi["non_official_amount"] == 33_250 and kpi["non_official_entries"] == 1
    assert panel.kpis["commission_amount"].cget("text") == "3.000 Gs."
    assert panel.warning.winfo_ismapped()
    warning = panel.warning.cget("text")
    assert "33.250 Gs." in warning and "política anterior" in warning
    # El resumen por vendedora tampoco mezcla los dos importes.
    bucket = next(row for row in panel.report["by_saleswoman"] if row["saleswoman"] == "Vendedora Dos")
    assert bucket["commission_amount"] == 0 and bucket["non_official_amount"] == 33_250
    # Y el desglose de esa fila lo dice sin ambigüedad.
    panel.tree.selection_set(entry_id); panel.tree.event_generate("<<TreeviewSelect>>"); root.update()
    assert "no pagable" in panel.breakdown.winfo_children()[-1].winfo_children()[0].cget("text")
