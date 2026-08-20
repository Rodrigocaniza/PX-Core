# -*- coding: utf-8 -*-
"""La sección «Comisiones de composturas», manejada como la maneja el admin.

No se comprueba que la pantalla sea linda: se comprueba que lo que muestra sea
lo que el servicio dice, que los totales de abajo cuadren con las filas de
arriba, y que la pestaña no sea la que decide quién puede entrar. Si no hay
entorno gráfico estas pruebas se saltean solas; las del servicio, que son las
que fijan el comportamiento, corren siempre.
"""

from __future__ import annotations

import pytest

from modulos.caja_diaria.application.admin_ops import ROL_OPERADOR, AdminOperations
from modulos.caja_diaria.application.service_jobs import ServiceJobsService
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

CLAVE_SOL = "administradora-2026"
CLAVE_LETI = "operadora-leti-2026"
COMISION = 5_000


@pytest.fixture()
def escenario(tmp_path):
    repo = SQLiteCashDayRepository(tmp_path / "bc_caja.sqlite3")
    repo.bind_register_to_branch("PC", "ASUNCION", assigned_by="admin")
    admin = AdminOperations(repo, tmp_path / "datos")
    sol = admin.create_initial_admin("sol", CLAVE_SOL)
    admin.create_user(sol.token, username="leti", display_name="Leti",
                      role=ROL_OPERADOR, branch="ASUNCION", password=CLAVE_LETI)
    rita = admin.create_user(sol.token, username="rita", display_name="Rita",
                             role=ROL_OPERADOR, branch="ASUNCION")
    servicio = ServiceJobsService(repo, admin_ops=admin)
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION,
                              job_type="COMPOSTURA")
    yield dict(repo=repo, admin=admin, sol=sol, rita=rita, servicio=servicio)
    repo.close()


@pytest.fixture(scope="module")
def raiz():
    """Un solo Tk para todo el módulo, igual que en Composturas."""
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
def panel(raiz, escenario):
    from modulos.caja_diaria.ui.commission_panel import PanelComisiones

    widget = PanelComisiones(raiz, escenario["servicio"],
                             token=escenario["sol"].token, ventana=raiz)
    try:
        yield widget
    finally:
        widget.destroy()


def terminado(servicio, **extras):
    datos = dict(customer_name="Sra. López", description="Soldar el frente",
                 job_type="COMPOSTURA", actor="Leti", branch="ASUNCION",
                 responsible="Rita")
    datos.update(extras)
    trabajo = servicio.crear_trabajo(**datos)
    return servicio.marcar_listo(trabajo.id, actor="Rita")


def filas(tabla):
    return [tabla.item(iid)["values"] for iid in tabla.get_children()]


# ==========================================================================
# Política
# ==========================================================================

def test_la_tabla_muestra_la_politica_cargada(panel, escenario):
    [fila] = filas(panel.tabla)
    assert fila[0] == "Rita"
    assert fila[1] == "Todas"          # sin sucursal: política común
    assert fila[2] == "COMPOSTURA"
    assert str(fila[3]) == "5.000"
    assert fila[5] == "Activa"
    assert fila[6] == "sol"


def test_una_politica_desactivada_se_sigue_viendo(panel, escenario):
    """Esconderla dejaría al administrador creyendo que nunca se cargó."""
    escenario["servicio"].desactivar_comision(
        token=escenario["sol"].token, user_id=escenario["rita"].id,
        job_type="COMPOSTURA", reason="Pasa a sueldo fijo")
    panel.refrescar()
    [fila] = filas(panel.tabla)
    assert fila[5] == "Inactiva"


def test_las_personas_del_selector_salen_del_catalogo_real(panel, escenario):
    assert [persona["display_name"] for persona in panel._personas] == [
        "Leti", "Rita", "sol"]


# ==========================================================================
# Reporte
# ==========================================================================

def test_el_reporte_muestra_devengado_compensado_y_neto(panel, escenario):
    terminado(escenario["servicio"])
    panel.consultar()
    [fila] = filas(panel.reporte)
    assert fila[3] == "Rita"
    assert fila[4] == "ASUNCION"
    assert str(fila[5]) == "5.000"     # devengado
    assert fila[6] == "—"              # sin compensación
    assert str(fila[7]) == "5.000"     # neto
    assert fila[8] == "DEVENGADA"
    assert "NETO 5.000" in panel.totales.cget("text")


def test_un_trabajo_anulado_se_lee_compensado_y_con_neto_cero(panel, escenario):
    trabajo = terminado(escenario["servicio"])
    escenario["servicio"].anular(trabajo.id, actor="Sol", reason="No lo trajo")
    panel.consultar()
    [fila] = filas(panel.reporte)
    assert fila[8] == "COMPENSADA"
    assert str(fila[7]) == "0"
    assert "NETO 0" in panel.totales.cget("text")


def test_los_totales_cuadran_con_las_filas_de_arriba(panel, escenario):
    for _ in range(3):
        terminado(escenario["servicio"])
    panel.consultar()
    assert len(filas(panel.reporte)) == 3
    assert "3 trabajos" in panel.totales.cget("text")
    assert "NETO 15.000" in panel.totales.cget("text")


def test_lo_que_no_devengo_se_avisa_en_vez_de_quedar_callado(panel, escenario):
    """Un trabajo terminado sin comisión puede ser decisión o ser olvido."""
    admin, sol = escenario["admin"], escenario["sol"]
    admin.create_user(sol.token, username="cami", display_name="Cami",
                      role=ROL_OPERADOR, branch="ASUNCION")
    terminado(escenario["servicio"], responsible="Cami")
    panel.consultar()
    assert filas(panel.reporte) == []
    assert "no devengaron" in panel.pendiente.cget("text")


def test_sin_pendientes_el_aviso_queda_vacio(panel, escenario):
    terminado(escenario["servicio"])
    panel.consultar()
    assert panel.pendiente.cget("text") == ""


# ==========================================================================
# Rol
# ==========================================================================

def test_el_panel_no_puede_leerse_con_una_sesion_de_operadora(raiz, escenario, monkeypatch):
    """La pantalla no autoriza: pide, y el servicio contesta que no.

    Se arma el panel con el token de Leti y lo que tiene que pasar es que no
    muestre nada y avise, no que muestre la política de las demás.
    """
    from modulos.caja_diaria.ui import commission_panel

    errores = []
    monkeypatch.setattr(commission_panel.PanelComisiones, "_fallar",
                        lambda self, error: errores.append(str(error)))
    sesion = escenario["admin"].authenticate("leti", CLAVE_LETI)
    widget = commission_panel.PanelComisiones(
        raiz, escenario["servicio"], token=sesion.token, ventana=raiz)
    try:
        assert filas(widget.tabla) == []
        assert errores, "una sesión sin rol tiene que fallar, no mostrar la política"
        widget.consultar()
        assert len(errores) >= 2
    finally:
        widget.destroy()
