# -*- coding: utf-8 -*-
"""La pestaña Composturas, manejada como la maneja la operadora.

No se comprueba que la pantalla sea linda: se comprueba que lo que hay para
apretar haga lo que dice, y que no ofrezca lo que después va a fallar. Si no hay
entorno gráfico estas pruebas se saltean solas; las del servicio, que son las
que fijan el comportamiento, corren siempre.
"""

from __future__ import annotations

import pytest

from modulos.caja_diaria.application.admin_ops import ROL_OPERADOR, AdminOperations
from modulos.caja_diaria.application.service_jobs import (
    ServiceJobsService,
    VISTA_LISTOS,
    VISTA_PENDIENTES,
    VISTA_TODOS,
)
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

OPERADORA = "Leti"


@pytest.fixture()
def servicio(tmp_path):
    repo = SQLiteCashDayRepository(tmp_path / "bc_caja.sqlite3")
    repo.bind_register_to_branch("PC", "ASUNCION", assigned_by="admin")
    admin = AdminOperations(repo, tmp_path / "datos")
    sol = admin.create_initial_admin("sol", "administradora-2026")
    admin.create_user(sol.token, username="rita", display_name="Rita",
                      role=ROL_OPERADOR, branch="ASUNCION")
    yield ServiceJobsService(repo, admin_ops=admin)
    repo.close()


@pytest.fixture(scope="module")
def raiz():
    """Un solo Tk para todo el módulo, por la misma razón que en FactuFácil."""
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
    from modulos.caja_diaria.ui.service_jobs_panel import PanelComposturas

    widget = PanelComposturas(raiz, servicio, actor=lambda: OPERADORA,
                              sucursal=lambda: "ASUNCION")
    try:
        yield widget
    finally:
        widget.destroy()


def alta(servicio, **extras):
    datos = dict(customer_name="Sra. López", description="Soldar el frente",
                 job_type="COMPOSTURA", actor=OPERADORA, branch="ASUNCION")
    datos.update(extras)
    return servicio.crear_trabajo(**datos)


def elegir(panel, job_id):
    panel._tabla.selection_set(job_id)
    panel._ajustar_acciones()


def test_abre_en_los_listos_para_entregar(panel):
    """La pregunta que el mostrador hace todo el día, contestada al entrar."""
    assert panel._vista.get() == VISTA_LISTOS


def test_la_lista_muestra_lo_que_la_operadora_lee(panel, servicio):
    trabajo = alta(servicio, customer_phone="0981-111222")
    panel._cambiar_vista(VISTA_PENDIENTES)
    valores = panel._tabla.item(trabajo.id)["values"]
    assert valores[0] == trabajo.reference
    assert valores[1] == "Sra. López"
    assert valores[2] == "0981-111222"
    assert "RECIBIDO" in valores


def test_sin_fila_elegida_no_hay_accion_habilitada(panel, servicio):
    alta(servicio)
    panel._cambiar_vista(VISTA_PENDIENTES)
    assert all(boton.cget("state") == "disabled"
               for boton in panel._acciones.values())


def test_solo_se_habilita_lo_que_el_trabajo_admite(panel, servicio):
    trabajo = alta(servicio)
    panel._cambiar_vista(VISTA_PENDIENTES)
    elegir(panel, trabajo.id)
    assert panel._acciones["taller"].cget("state") == "normal"
    assert panel._acciones["listo"].cget("state") == "normal"
    assert panel._acciones["anular"].cget("state") == "normal"
    # Entregar algo que todavía no está listo no se ofrece siquiera.
    assert panel._acciones["entregar"].cget("state") == "disabled"


def test_un_entregado_no_ofrece_volver_a_entregar(panel, servicio):
    trabajo = alta(servicio)
    servicio.marcar_listo(trabajo.id, actor=OPERADORA)
    servicio.entregar(trabajo.id, actor=OPERADORA)
    panel._cambiar_vista(VISTA_TODOS)
    elegir(panel, trabajo.id)
    assert panel._acciones["entregar"].cget("state") == "disabled"
    assert panel._acciones["listo"].cget("state") == "disabled"


def test_el_boton_dice_reabrir_cuando_reabre(panel, servicio):
    """Volver al taller desde LISTO no es enviar: se dice antes de apretar."""
    trabajo = alta(servicio)
    panel._cambiar_vista(VISTA_PENDIENTES)
    elegir(panel, trabajo.id)
    assert panel._acciones["taller"].cget("text") == "Enviar a taller"
    servicio.marcar_listo(trabajo.id, actor=OPERADORA)
    panel.refrescar()
    elegir(panel, trabajo.id)
    assert panel._acciones["taller"].cget("text") == "Reabrir"


def test_marcar_listo_desde_la_pantalla_mueve_el_trabajo(panel, servicio):
    trabajo = alta(servicio)
    panel._cambiar_vista(VISTA_PENDIENTES)
    elegir(panel, trabajo.id)
    panel.marcar_listo()
    assert servicio.obtener(trabajo.id).status.value == "LISTO"


def test_lo_que_se_hace_desde_la_pantalla_queda_a_nombre_de_quien_opera(panel, servicio):
    trabajo = alta(servicio)
    panel._cambiar_vista(VISTA_PENDIENTES)
    elegir(panel, trabajo.id)
    panel.marcar_listo()
    ultimo = servicio.historial(trabajo.id)[-1]
    assert ultimo.actor == OPERADORA


def test_el_resumen_cuenta_lo_que_hay(panel, servicio):
    alta(servicio)
    listo = alta(servicio, customer_name="Otro")
    servicio.marcar_listo(listo.id, actor=OPERADORA)
    panel.refrescar()
    assert "1 recibidos" in panel._resumen.cget("text")
    assert "1 listos" in panel._resumen.cget("text")


def test_una_vista_vacia_lo_dice_en_vez_de_quedar_en_blanco(panel):
    panel._cambiar_vista(VISTA_PENDIENTES)
    assert "No hay trabajos" in panel._vacio.cget("text")


def test_los_trabajos_de_otra_sucursal_no_aparecen(panel, servicio):
    alta(servicio, branch="PILAR", customer_name="De Pilar")
    panel._cambiar_vista(VISTA_TODOS)
    assert panel._tabla.get_children() == ()
    # Destildar «solo mi sucursal» es la salida explícita a la vista global.
    panel._solo_mi_sucursal.set(False)
    panel.refrescar()
    assert len(panel._tabla.get_children()) == 1
