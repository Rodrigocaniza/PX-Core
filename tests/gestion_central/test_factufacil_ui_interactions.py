import tkinter as tk

import pytest

from bc_gestion_central import build_service
from modulos.gestion_central.factufacil import FactuFacilSale,FactuFacilService
from modulos.gestion_central.ui import CentralPilotWindow


@pytest.fixture(scope="module")
def root():value=tk.Tk();value.withdraw();yield value;value.destroy()


@pytest.fixture
def app(tmp_path,root):
    core=build_service(tmp_path);core.bootstrap_synthetic_pilot();sol=core.authenticate("sol.piloto","Piloto-Temporal-2026");ff=FactuFacilService(core)
    sale=FactuFacilSale("Casa Central","sale-ui","Cliente Sintético","RUC-UI","B-UI","2099-04-11","CAJA-01","S-UI","Receta línea 1\nReceta línea 2",({"description":"Artículo UI","price":750000},),750000,"EFECTIVO",750000,0,"Vendedora UI")
    sale_id,_=ff.register(sol,sale);window=CentralPilotWindow(core,root=root,notifier=lambda *_:None);root.update();yield window,ff,sale_id;window.content.destroy()


def test_navigation_filters_detail_copy_and_back(app,root):
    window,_,sale_id=app;window.factufacil_button.invoke();root.update();panel=window.factufacil_panel
    assert window.current_screen=="factufacil" and panel.tree.get_children()==(sale_id,)
    panel.tree.selection_set(sale_id);panel.tree.event_generate("<<TreeviewSelect>>");root.update();assert "Receta línea 1" in " ".join(child.get("1.0","end") for block in panel.detail.winfo_children() for child in block.winfo_children() if isinstance(child,tk.Text))
    panel.copy_all();root.update();assert "Observaciones / receta: Receta línea 1\nReceta línea 2" in root.clipboard_get()
    panel.customer_var.set("Sin coincidencia");panel.reload();assert not panel.tree.get_children();panel.back();root.update();assert window.current_screen=="dashboard"


def test_full_hd_controls_visible(app,root):
    window,_,sale_id=app;window.show_factufacil();root.deiconify();root.geometry("1920x1080");root.update();panel=window.factufacil_panel;panel.tree.selection_set(sale_id);panel.tree.event_generate("<<TreeviewSelect>>");root.update()
    assert panel.tree.winfo_width()>=800 and panel.loaded_button.winfo_viewable() and panel.revert_button.winfo_viewable()
