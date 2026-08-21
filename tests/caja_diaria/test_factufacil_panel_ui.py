# -*- coding: utf-8 -*-
"""La pestaña FactuFácil, manejada como la maneja la operadora.

No se comprueba que la pantalla sea linda: se comprueba que hacer clic en lo que
hay haga lo que dice. Si no hay entorno gráfico, estas pruebas se saltean solas;
las del servicio, que son las que fijan el comportamiento, corren siempre.
"""

from __future__ import annotations

from datetime import date

import pytest

from modulos.caja_diaria.application.factufacil import (
    CARGADA,
    PARA_CARGAR,
    FactuFacilService,
)
from modulos.caja_diaria.domain.models import CashDay, CashEntry
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

ACTOR = "rosa"
RECETA = ("OD esf -2.00 cil -0.75 eje 90 · OI esf -1.75 cil -0.50 eje 85 · "
          "adición 2.00 · armazón del cliente")


@pytest.fixture()
def servicio(tmp_path):
    repo = SQLiteCashDayRepository(tmp_path / "bc_caja.sqlite3")
    repo.bind_register_to_branch("PC", "ASUNCION", assigned_by="admin")
    repo.save(CashDay(
        business_date=date(2026, 8, 19), unit="PC", opening_cash=0, opened_by=ACTOR,
        entries=(
            CashEntry(description="Maria Gonzalez", envelope="1001", total=450000,
                      cash=450000, saleswoman="ana", customer_document="1234567",
                      customer_phone="0981111222", observations=RECETA),
            CashEntry(description="Jose Ramirez", envelope="1002", total=300000,
                      cash=300000, saleswoman="rosa", customer_document="7654321"),
        )))
    yield FactuFacilService(repo)
    repo.close()


@pytest.fixture(scope="module")
def raiz():
    """Un solo Tk para todo el módulo.

    Crear y destruir un root por prueba agota los intérpretes Tcl en Windows, y
    entonces alguna prueba se saltea sin razón. Compartir el root las hace
    determinísticas; cada una arma su panel y lo destruye.
    """
    ctk = pytest.importorskip("customtkinter")
    try:
        ventana = ctk.CTk()
    except Exception as error:  # pragma: no cover - sin entorno gráfico
        pytest.skip(f"sin entorno gráfico: {error}")
    ventana.withdraw()
    try:
        yield ventana
    finally:
        ventana.destroy()


@pytest.fixture()
def panel(raiz, servicio):
    from modulos.caja_diaria.ui.factufacil_panel import PanelFactuFacil

    copiado = []
    widget = PanelFactuFacil(raiz, servicio, actor=ACTOR, copiar=copiado.append)
    widget.copiado = copiado
    try:
        yield widget
    finally:
        widget.destroy()


def _seleccionar(panel, indice=0):
    hijos = panel.tabla.get_children()
    panel.tabla.selection_set(hijos[indice])
    panel._al_seleccionar()
    return hijos[indice]


def test_abre_mostrando_lo_que_falta_cargar(panel):
    """Entrar a la pestaña ya responde la pregunta, sin tocar un filtro."""
    assert len(panel.tabla.get_children()) == 2
    chip, _ = panel._chips[PARA_CARGAR]
    assert "PARA CARGAR  (2)" in chip.cget("text")
    assert "CARGADA  (0)" in panel._chips[CARGADA][0].cget("text")


def test_sin_fila_elegida_los_botones_no_hacen_nada(panel):
    for boton in (panel.boton_copiar, panel.boton_marcar, panel.boton_revertir):
        assert boton.cget("state") == "disabled"


def test_elegir_una_fila_habilita_copiar_y_marcar(panel):
    _seleccionar(panel)
    assert panel.boton_copiar.cget("state") == "normal"
    assert panel.boton_marcar.cget("state") == "normal"
    assert panel.boton_revertir.cget("state") == "disabled", "todavía no está cargada"


def test_la_receta_se_ve_entera_al_elegir_la_fila(panel):
    _seleccionar(panel)
    texto = panel.observaciones.get("1.0", "end").strip()
    assert texto == RECETA, "la receta no se corta ni se abrevia"


def test_copiar_deja_los_datos_en_el_portapapeles_y_avisa(panel):
    _seleccionar(panel)
    panel.copiar_seleccion()
    assert len(panel.copiado) == 1
    for rotulo in ("Cliente:", "CI/RUC:", "Sobre:", "Total:", "Observaciones:"):
        assert rotulo in panel.copiado[0]
    assert "copiados" in panel.mensaje.cget("text").lower()


def test_marcar_mueve_la_fila_de_lista_y_lo_dice(panel):
    _seleccionar(panel)
    panel.marcar_seleccion()
    assert len(panel.tabla.get_children()) == 1, "salió de PARA CARGAR"
    assert "1001" in panel.mensaje.cget("text")
    panel._cambiar_estado(CARGADA)
    assert len(panel.tabla.get_children()) == 1
    valores = panel.tabla.item(panel.tabla.get_children()[0], "values")
    assert valores[0] == "CARGADA" and valores[-1] == ACTOR


def test_marcar_de_nuevo_avisa_que_ya_estaba(panel, servicio):
    fila = servicio.listar()[0]
    servicio.marcar_cargada(fila.cash_entry_id, actor="otra")
    panel._cambiar_estado(CARGADA)
    _seleccionar(panel)
    panel.marcar_seleccion()
    assert "ya estaba" in panel.mensaje.cget("text")


def test_revertir_sin_motivo_no_revierte(panel, servicio, monkeypatch):
    fila = servicio.listar()[0]
    servicio.marcar_cargada(fila.cash_entry_id, actor="otra")
    panel._cambiar_estado(CARGADA)
    _seleccionar(panel)
    monkeypatch.setattr(
        "modulos.caja_diaria.ui.factufacil_panel.ctk.CTkInputDialog",
        lambda **_kwargs: type("D", (), {"get_input": lambda self: ""})())
    panel.revertir_seleccion()
    assert servicio.obtener(fila.cash_entry_id).estado == CARGADA
    assert "Sin motivo" in panel.mensaje.cget("text")


def test_revertir_con_motivo_la_devuelve_a_para_cargar(panel, servicio, monkeypatch):
    fila = servicio.listar()[0]
    servicio.marcar_cargada(fila.cash_entry_id, actor="otra")
    panel._cambiar_estado(CARGADA)
    _seleccionar(panel)
    monkeypatch.setattr(
        "modulos.caja_diaria.ui.factufacil_panel.ctk.CTkInputDialog",
        lambda **_kwargs: type("D", (), {"get_input": lambda self: "sobre equivocado"})())
    panel.revertir_seleccion()
    assert servicio.obtener(fila.cash_entry_id).estado == PARA_CARGAR
    assert ff_motivo(servicio, fila.cash_entry_id) == "sobre equivocado"


def ff_motivo(servicio, entry_id):
    return servicio.historial(entry_id)[-1]["reason"]


def test_los_filtros_recortan_la_lista(panel):
    panel._entradas["sobre"].insert(0, "1002")
    panel.refrescar()
    assert len(panel.tabla.get_children()) == 1
    panel._limpiar_filtros()
    assert len(panel.tabla.get_children()) == 2


def test_el_boton_hoy_filtra_por_la_fecha_de_hoy(panel):
    panel._filtrar_hoy()
    hoy = date.today().isoformat()
    assert panel._entradas["desde"].get() == hoy
    # El día de prueba es el 19/08/2026, así que hoy no trae nada: lo que se
    # comprueba es que el atajo filtre, no que haya ventas.
    assert len(panel.tabla.get_children()) == 0 or hoy == "2026-08-19"


def test_no_se_ve_un_solo_codigo_interno(panel):
    """Ningún id de base de datos llega a la pantalla."""
    for iid in panel.tabla.get_children():
        for valor in panel.tabla.item(iid, "values"):
            assert iid not in str(valor), "un uuid se filtró a una celda"


def test_una_venta_editada_despues_de_cargar_se_marca_en_la_grilla(panel, servicio):
    entrada = servicio.listar()[0]
    servicio.marcar_cargada(entrada.cash_entry_id, actor="otra")
    with servicio._repository._connection() as con:
        con.execute("UPDATE cash_entries SET revision = revision + 1 WHERE id = ?",
                    (entrada.cash_entry_id,))
        con.commit()
    panel._cambiar_estado(CARGADA)
    assert "editada" in panel.tabla.item(entrada.cash_entry_id, "tags")
    assert "editaron" in panel._aviso.cget("text")
