# -*- coding: utf-8 -*-
"""V1-018: los dos cierres de Seguimiento, y cuál es cuál.

El circuito termina cuando el trabajo vuelve a Pilar. Archivarlo después es
guardar algo que salió bien, y no pide motivo. Cerrar por excepción es la salida
de lo que **no** llegó a terminar —una cancelación, una devolución, una
corrección administrativa— y sí lo pide.

Lo que se fija acá es que esos dos caminos no se confundan: que el normal exista
y no exija justificar nada, que el de excepción siga exigiéndolo, y sobre todo
que el normal no pueda usarse para cerrar en silencio un trabajo que quedó a
mitad de camino.
"""

from __future__ import annotations

from datetime import date, time

import pytest

from modulos.caja_diaria.application.tracking_service import TrackingService
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.tracking import Laboratory, TrackingStatus
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

NIDIA = "nidia"
HOY = date.today()


@pytest.fixture()
def ruta(tmp_path):
    return tmp_path / "bc_caja.sqlite3"


@pytest.fixture()
def repo(ruta):
    repositorio = SQLiteCashDayRepository(ruta)
    yield repositorio
    repositorio.close()


@pytest.fixture()
def seguimiento(repo):
    return TrackingService(repo)


@pytest.fixture()
def laboratorio(repo):
    return repo.save_laboratory(Laboratory(name="Laboratorio Optilab"))


def _nuevo(seguimiento, sobre="4001"):
    return seguimiento.register_pilar_batch(
        [{"envelope": sobre, "customer_name": "Maria Gonzalez"}],
        consultation_date=HOY, created_by=NIDIA)[0]


def _hasta_pilar(seguimiento, laboratorio, sobre="4001"):
    """El circuito completo, por el camino real. Termina en RECIBIDO EN PILAR."""
    trabajo = _nuevo(seguimiento, sobre)
    seguimiento.receive_in_asuncion(trabajo.id, responsible=NIDIA)
    seguimiento.send_to_laboratory(
        trabajo.id, laboratorio.id, expected_date=HOY, expected_time=time(17, 0),
        responsible=NIDIA)
    seguimiento.receive_from_laboratory(trabajo.id, responsible=NIDIA)
    seguimiento.send_batch_to_pilar([trabajo.id], responsible=NIDIA)
    seguimiento.receive_in_pilar(trabajo.id, responsible=NIDIA)
    return seguimiento._load(trabajo.id)


# --------------------------------------------------------------------------
# 1. El flujo normal llega al final previsto
# --------------------------------------------------------------------------

def test_el_circuito_termina_cuando_el_trabajo_vuelve_a_pilar(seguimiento,
                                                              laboratorio):
    trabajo = _hasta_pilar(seguimiento, laboratorio)
    assert trabajo.status is TrackingStatus.RECEIVED_IN_PILAR
    # Y ahí no falta nada: la pantalla no pide ninguna acción siguiente.
    assert seguimiento.next_action_for([trabajo.id])["action"].name == "NONE"


def test_un_trabajo_terminado_ya_cuenta_como_completado_sin_archivarlo(
        seguimiento, laboratorio, repo):
    """Archivar es opcional. Un trabajo que volvió a Pilar ya está fuera de lo
    pendiente, y por eso nadie está obligado a cerrarlo."""
    from modulos.caja_diaria.application.tracking_service import GRUPO_DE_ETAPA

    trabajo = _hasta_pilar(seguimiento, laboratorio)
    assert GRUPO_DE_ETAPA[trabajo.status] == "completados"
    assert GRUPO_DE_ETAPA[TrackingStatus.CLOSED] == "completados", (
        "archivado y terminado son el mismo grupo para la operadora")


# --------------------------------------------------------------------------
# 2-3. El cierre normal
# --------------------------------------------------------------------------

def test_el_cierre_normal_no_exige_motivo(seguimiento, laboratorio):
    trabajo = _hasta_pilar(seguimiento, laboratorio)
    cerrado = seguimiento.close_work(trabajo.id, responsible=NIDIA)
    assert cerrado.status is TrackingStatus.CLOSED


def test_el_cierre_normal_queda_auditado(seguimiento, laboratorio):
    trabajo = _hasta_pilar(seguimiento, laboratorio)
    seguimiento.close_work(trabajo.id, responsible=NIDIA)
    ultima = seguimiento._load(trabajo.id).transitions[-1]
    assert ultima.from_status is TrackingStatus.RECEIVED_IN_PILAR
    assert ultima.to_status is TrackingStatus.CLOSED
    assert ultima.responsible == NIDIA
    assert ultima.recorded_at is not None


def test_el_cierre_normal_no_se_disfraza_de_excepcion(seguimiento, laboratorio):
    """Nada de «Cierre por excepción:» en la traza de algo que salió bien."""
    trabajo = _hasta_pilar(seguimiento, laboratorio)
    seguimiento.close_work(trabajo.id, responsible=NIDIA)
    assert "excepción" not in seguimiento._load(trabajo.id).transitions[-1].note


def test_el_cierre_normal_exige_responsable(seguimiento, laboratorio):
    """No pedir motivo no es no pedir nada: quién archivó sigue siendo un dato."""
    trabajo = _hasta_pilar(seguimiento, laboratorio)
    with pytest.raises(InvalidCashDayError):
        seguimiento.close_work(trabajo.id, responsible="   ")


# --------------------------------------------------------------------------
# 4-6. La excepción sigue siendo excepción
# --------------------------------------------------------------------------

def test_la_excepcion_sigue_exigiendo_motivo(seguimiento, laboratorio):
    trabajo = _hasta_pilar(seguimiento, laboratorio)
    with pytest.raises(InvalidCashDayError, match="motivo"):
        seguimiento.close_by_exception(trabajo.id, responsible=NIDIA, reason="  ")


def test_la_excepcion_deja_el_motivo_escrito(seguimiento, laboratorio):
    trabajo = _nuevo(seguimiento)
    seguimiento.close_by_exception(
        trabajo.id, responsible=NIDIA, reason="el cliente canceló el pedido")
    ultima = seguimiento._load(trabajo.id).transitions[-1]
    assert ultima.to_status is TrackingStatus.CLOSED
    assert "el cliente canceló el pedido" in ultima.note
    assert "Cierre por excepción" in ultima.note


def test_el_cierre_normal_NO_puede_cerrar_algo_a_mitad_de_camino(seguimiento,
                                                                 laboratorio):
    """La guarda que importa. Si el normal pudiera cerrar desde cualquier etapa,
    un trabajo perdido en el laboratorio desaparecería sin que nadie explique
    nada — y ésa es justamente la diferencia entre los dos cierres."""
    trabajo = _nuevo(seguimiento)
    seguimiento.receive_in_asuncion(trabajo.id, responsible=NIDIA)
    seguimiento.send_to_laboratory(
        trabajo.id, laboratorio.id, expected_date=HOY, expected_time=time(17, 0),
        responsible=NIDIA)
    with pytest.raises(InvalidCashDayError, match="transicion invalida"):
        seguimiento.close_work(trabajo.id, responsible=NIDIA)
    assert seguimiento._load(trabajo.id).status is TrackingStatus.IN_LABORATORY
    # Para eso está la excepción, y ahí sí hay que decir por qué.
    seguimiento.close_by_exception(
        trabajo.id, responsible=NIDIA, reason="el laboratorio lo perdió")
    assert seguimiento._load(trabajo.id).status is TrackingStatus.CLOSED


def test_una_etapa_intermedia_tampoco_se_archiva(seguimiento, laboratorio):
    trabajo = _nuevo(seguimiento)
    seguimiento.receive_in_asuncion(trabajo.id, responsible=NIDIA)
    with pytest.raises(InvalidCashDayError):
        seguimiento.close_work(trabajo.id, responsible=NIDIA)


# --------------------------------------------------------------------------
# 7. No se cierra dos veces
# --------------------------------------------------------------------------

def test_un_trabajo_ya_archivado_no_vuelve_a_archivarse(seguimiento, laboratorio):
    trabajo = _hasta_pilar(seguimiento, laboratorio)
    seguimiento.close_work(trabajo.id, responsible=NIDIA)
    with pytest.raises(InvalidCashDayError):
        seguimiento.close_work(trabajo.id, responsible=NIDIA)
    assert len(seguimiento._load(trabajo.id).transitions) == 6


def test_un_trabajo_ya_archivado_tampoco_se_cierra_por_excepcion(seguimiento,
                                                                 laboratorio):
    trabajo = _hasta_pilar(seguimiento, laboratorio)
    seguimiento.close_work(trabajo.id, responsible=NIDIA)
    with pytest.raises(InvalidCashDayError, match="ya está cerrado"):
        seguimiento.close_by_exception(
            trabajo.id, responsible=NIDIA, reason="por las dudas")


# --------------------------------------------------------------------------
# 8. Asunción no cambia
# --------------------------------------------------------------------------

def test_el_tramo_de_asuncion_sigue_igual(seguimiento, laboratorio):
    """El circuito no tiene matrices por sucursal: es uno solo, y la sucursal
    responsable se deriva de la etapa. Archivar no toca ninguna de esas etapas."""
    from modulos.caja_diaria.domain.tracking import ALLOWED_TRANSITIONS

    assert ALLOWED_TRANSITIONS[TrackingStatus.SENT_FROM_PILAR] == (
        TrackingStatus.RECEIVED_IN_ASUNCION,)
    assert ALLOWED_TRANSITIONS[TrackingStatus.RECEIVED_IN_ASUNCION] == (
        TrackingStatus.IN_LABORATORY,)
    assert ALLOWED_TRANSITIONS[TrackingStatus.IN_LABORATORY] == (
        TrackingStatus.RECEIVED_FROM_LABORATORY,)
    assert ALLOWED_TRANSITIONS[TrackingStatus.RECEIVED_IN_PILAR] == (
        TrackingStatus.CLOSED,)


def test_archivar_no_saltea_ninguna_etapa(seguimiento, laboratorio):
    trabajo = _hasta_pilar(seguimiento, laboratorio)
    seguimiento.close_work(trabajo.id, responsible=NIDIA)
    recorrido = [t.to_status for t in seguimiento._load(trabajo.id).transitions]
    assert recorrido == [
        TrackingStatus.RECEIVED_IN_ASUNCION, TrackingStatus.IN_LABORATORY,
        TrackingStatus.RECEIVED_FROM_LABORATORY, TrackingStatus.SENT_TO_PILAR,
        TrackingStatus.RECEIVED_IN_PILAR, TrackingStatus.CLOSED]


# --------------------------------------------------------------------------
# 9-10. Persistencia e historia
# --------------------------------------------------------------------------

def test_reiniciar_la_app_conserva_el_archivado(ruta, repo, seguimiento,
                                                laboratorio):
    trabajo = _hasta_pilar(seguimiento, laboratorio)
    seguimiento.close_work(trabajo.id, responsible=NIDIA)
    repo.close()
    otro = SQLiteCashDayRepository(ruta)
    try:
        recargado = TrackingService(otro)._load(trabajo.id)
        assert recargado.status is TrackingStatus.CLOSED
        assert recargado.transitions[-1].responsible == NIDIA
        assert len(recargado.transitions) == 6
    finally:
        otro.close()


def test_archivar_no_reescribe_la_historia_anterior(seguimiento, laboratorio):
    trabajo = _hasta_pilar(seguimiento, laboratorio)
    antes = [(t.from_status, t.to_status, t.responsible, t.note)
             for t in seguimiento._load(trabajo.id).transitions]
    seguimiento.close_work(trabajo.id, responsible="otra")
    despues = [(t.from_status, t.to_status, t.responsible, t.note)
               for t in seguimiento._load(trabajo.id).transitions]
    assert despues[:len(antes)] == antes


def test_los_cerrados_por_excepcion_de_antes_siguen_diciendo_lo_mismo(
        seguimiento, laboratorio):
    """La regla nueva es hacia adelante: lo ya cerrado por excepción queda."""
    viejo = _nuevo(seguimiento, "4009")
    seguimiento.close_by_exception(
        viejo.id, responsible=NIDIA, reason="cancelado en agosto")
    nuevo = _hasta_pilar(seguimiento, laboratorio)
    seguimiento.close_work(nuevo.id, responsible=NIDIA)
    assert "cancelado en agosto" in seguimiento._load(viejo.id).transitions[-1].note
    assert seguimiento._load(viejo.id).status is TrackingStatus.CLOSED


# --------------------------------------------------------------------------
# 11-12. Nada económico ni de stock
# --------------------------------------------------------------------------

def test_archivar_no_toca_ni_stock_ni_dinero(repo, seguimiento, laboratorio):
    trabajo = _hasta_pilar(seguimiento, laboratorio)

    def foto():
        with repo._connection() as con:
            q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
            return dict(
                movimientos=q("SELECT COUNT(*) FROM stock_movements"),
                stock=q("SELECT COALESCE(SUM(quantity),0) FROM stock_actual"),
                entradas=q("SELECT COUNT(*) FROM cash_entries"),
                caja=q("SELECT COALESCE(SUM(total),0) FROM cash_entries"),
                sale_items=q("SELECT COUNT(*) FROM sale_items"),
                articulos=q("SELECT COUNT(*) FROM articles"),
                pedidos=q("SELECT COUNT(*) FROM orders"),
                laboratorios=q("SELECT COUNT(*) FROM laboratories"))

    antes = foto()
    seguimiento.close_work(trabajo.id, responsible=NIDIA)
    assert foto() == antes


# --------------------------------------------------------------------------
# 13. La pantalla distingue los dos
# --------------------------------------------------------------------------

FUENTE = open("CajaDiaria.py", encoding="utf-8").read()


def test_la_pantalla_ofrece_el_cierre_normal():
    assert "def archivar_completados():" in FUENTE
    assert 'menu.add_command(label="Archivar terminados"' in FUENTE
    bloque = FUENTE[FUENTE.index("def archivar_completados():"):][:2000]
    assert "controller.tracking.close_work(" in bloque
    assert "pedir_motivo" not in bloque, "archivar no puede pedir motivo"


def test_la_pantalla_no_deja_archivar_lo_que_no_termino():
    bloque = FUENTE[FUENTE.index("def archivar_completados():"):][:2000]
    assert "TrackingStatus.RECEIVED_IN_PILAR" in bloque
    assert "Cerrar por excepción" in bloque, (
        "cuando no se puede archivar, hay que decir cuál es el camino correcto")


def test_los_dos_cierres_siguen_siendo_dos_cosas_distintas():
    assert "def cerrar_por_excepcion():" in FUENTE
    excepcion = FUENTE[FUENTE.index("def cerrar_por_excepcion():"):][:1500]
    assert "pedir_motivo" in excepcion and "obligatorio" in excepcion
    # En el menú, el normal va antes que la excepción.
    menu = FUENTE[FUENTE.index("def abrir_menu_mas():"):][:1200]
    assert menu.index("Archivar terminados") < menu.index("Cerrar por excepción")
