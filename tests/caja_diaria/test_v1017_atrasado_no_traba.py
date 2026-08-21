# -*- coding: utf-8 -*-
"""V1-017: estar atrasado no puede impedir que el trabajo avance.

Estas pruebas se escribieron **desde el reporte de operación**, sin mirar las
que ya existían, para comprobar por evidencia y no por confianza si el circuito
todavía se traba. Recorren el caso completo contra una base real de SQLite: se
registra el trabajo, se lo despacha, se lo deja vencer, y se comprueba que
llegue a la óptica y siga hasta el final.

Se solapan a propósito con `test_rc26_flujo_no_se_traba.py`. Esa suite fija la
regla desde el lado del dominio; ésta la fija desde el lado de la operadora, y
que las dos digan lo mismo es parte de lo que se quería saber.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from modulos.caja_diaria.application.tracking_service import TrackingService
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import BUSINESS_TIMEZONE
from modulos.caja_diaria.domain.tracking import (
    Laboratory,
    NextAction,
    TrackingStatus,
)
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

ACTOR = "rosa"
HOY = date.today()
AYER = HOY - timedelta(days=1)
MANANA = HOY + timedelta(days=1)


def ahora(momento: date = HOY, hora: time = time(16, 0)) -> datetime:
    return datetime.combine(momento, hora).replace(tzinfo=BUSINESS_TIMEZONE)


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


def _en_laboratorio(seguimiento, laboratorio, *, vence: date, sobre="3001"):
    """Un trabajo hasta EN LABORATORIO, por el camino real de la operadora."""
    trabajo = seguimiento.register_pilar_batch(
        [{"envelope": sobre, "customer_name": "Maria Gonzalez"}],
        consultation_date=HOY, created_by=ACTOR)[0]
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR)  # recibir en Asunción
    seguimiento.send_to_laboratory(
        trabajo.id, laboratorio.id, expected_date=vence, expected_time=time(17, 0),
        responsible=ACTOR)
    return seguimiento._load(trabajo.id)


# --------------------------------------------------------------------------
# 11-12. Qué es ATRASADO
# --------------------------------------------------------------------------

def test_una_fecha_vencida_marca_atrasado_sin_mover_la_etapa(seguimiento, laboratorio):
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    assert trabajo.is_overdue(ahora()) is True
    assert trabajo.status is TrackingStatus.IN_LABORATORY, (
        "el atraso no puede reemplazar la etapa física")


def test_una_fecha_futura_no_marca_atrasado(seguimiento, laboratorio):
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=MANANA)
    assert trabajo.is_overdue(ahora()) is False
    assert trabajo.status is TrackingStatus.IN_LABORATORY


def test_atrasado_no_se_guarda_en_ningun_lado(seguimiento, laboratorio, repo):
    """Es derivado del plazo, no una columna. Si estuviera guardado, se podría
    quedar viejo — y un trabajo figuraría atrasado después de llegar."""
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    with repo._connection() as con:
        columnas = {f[1] for f in con.execute("PRAGMA table_info(tracked_works)")}
    assert not {c for c in columnas if "overdue" in c or "atras" in c}
    # Y se apaga solo con mover el reloj, sin tocar la base.
    assert trabajo.is_overdue(ahora(AYER - timedelta(days=1))) is False


# --------------------------------------------------------------------------
# 1-2. El bloqueo reportado
# --------------------------------------------------------------------------

def test_en_laboratorio_al_dia_puede_avanzar(seguimiento, laboratorio):
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=MANANA)
    info = seguimiento.next_action_for([trabajo.id], now=ahora())
    assert info["action"] is NextAction.RECEIVE_FROM_LABORATORY


def test_en_laboratorio_atrasado_TAMBIEN_puede_avanzar(seguimiento, laboratorio):
    """El caso exacto del reporte. Si esto falla, el circuito está trabado."""
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    info = seguimiento.next_action_for([trabajo.id], now=ahora())
    assert info["action"] is NextAction.RECEIVE_FROM_LABORATORY, (
        "un trabajo vencido dejó de ofrecer «recibir»: el circuito se traba")
    assert info["action"] is not NextAction.CONTACT_LABORATORY


def test_contactar_sigue_estando_pero_como_acompanante(seguimiento, laboratorio):
    atrasado = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    al_dia = _en_laboratorio(seguimiento, laboratorio, vence=MANANA, sobre="3002")
    con_atraso = seguimiento.next_action_for([atrasado.id], now=ahora())
    sin_atraso = seguimiento.next_action_for([al_dia.id], now=ahora())
    assert con_atraso["complementary"] is NextAction.CONTACT_LABORATORY
    assert con_atraso["complementary_label"]
    assert sin_atraso["complementary"] is None
    # Y la acción principal es la misma con atraso o sin él.
    assert con_atraso["action"] == sin_atraso["action"]


# --------------------------------------------------------------------------
# 4-5. Avanzar de verdad
# --------------------------------------------------------------------------

def test_el_trabajo_atrasado_llega_a_la_optica_y_queda_persistido(
        seguimiento, laboratorio):
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
    quedo = seguimiento._load(trabajo.id)
    assert quedo.status is TrackingStatus.RECEIVED_FROM_LABORATORY


def test_despues_de_llegar_deja_de_figurar_en_laboratorio(seguimiento, laboratorio):
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
    quedo = seguimiento._load(trabajo.id)
    assert quedo.status is not TrackingStatus.IN_LABORATORY
    assert quedo.is_overdue(ahora()) is False, (
        "ya llegó: el plazo del laboratorio dejó de correr")
    assert seguimiento.next_action_for([trabajo.id], now=ahora())["action"] \
        is NextAction.SEND_TO_PILAR


def test_el_trabajo_atrasado_termina_el_circuito_entero(seguimiento, laboratorio):
    """Llega, vuelve a Pilar y completa. El atraso no dejó nada trabado.

    `RECIBIDO EN PILAR` es el final del circuito físico: `CERRADO` es el
    archivado posterior y tiene su propio camino, con motivo y responsable. Por
    eso la última etapa no ofrece «acción siguiente» y eso es correcto."""
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    for esperado in (TrackingStatus.RECEIVED_FROM_LABORATORY,
                     TrackingStatus.SENT_TO_PILAR,
                     TrackingStatus.RECEIVED_IN_PILAR):
        seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
        assert seguimiento._load(trabajo.id).status is esperado
    assert (seguimiento.next_action_for([trabajo.id], now=ahora())["action"]
            is NextAction.NONE)


# --------------------------------------------------------------------------
# 6. La historia
# --------------------------------------------------------------------------

def test_haber_estado_atrasado_queda_demostrable_despues_de_llegar(
        seguimiento, laboratorio):
    """Las dos cosas a la vez: que llegó, y que había estado vencido."""
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
    quedo = seguimiento._load(trabajo.id)
    etapas = [t.to_status for t in quedo.transitions]
    assert TrackingStatus.IN_LABORATORY in etapas and \
        TrackingStatus.RECEIVED_FROM_LABORATORY in etapas
    # El plazo se borra al salir del laboratorio, y tiene que borrarse: si
    # quedara, el trabajo seguiría figurando atrasado después de llegar. Lo que
    # no puede pasar es que se pierda la evidencia, y por eso queda sellada en
    # la transición que lo terminó.
    assert quedo.expected_date is None
    llegada = quedo.transitions[-1]
    assert "Plazo comprometido" in llegada.note
    assert "tarde" in llegada.note, "no se puede demostrar que llegó atrasado"
    ultima = quedo.transitions[-1]
    assert ultima.responsible == ACTOR and ultima.recorded_at is not None


def test_avanzar_no_reescribe_las_transiciones_anteriores(seguimiento, laboratorio):
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    antes = [(t.from_status, t.to_status, t.responsible)
             for t in seguimiento._load(trabajo.id).transitions]
    seguimiento.apply_next_action([trabajo.id], responsible="ana", now=ahora())
    despues = [(t.from_status, t.to_status, t.responsible)
               for t in seguimiento._load(trabajo.id).transitions]
    assert despues[:len(antes)] == antes
    assert len(despues) == len(antes) + 1


# --------------------------------------------------------------------------
# 7-9. Lo que sigue bloqueado, y tiene que seguir bloqueado
# --------------------------------------------------------------------------

def test_una_transicion_invalida_sigue_bloqueada(seguimiento, laboratorio):
    """Saltar del laboratorio directo a Pilar nunca fue válido, y el atraso no
    lo vuelve válido."""
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    with pytest.raises(InvalidCashDayError):
        seguimiento._advance(trabajo.id, TrackingStatus.SENT_TO_PILAR,
                             responsible=ACTOR)


def test_un_trabajo_cerrado_no_revive(seguimiento, laboratorio):
    """Cerrar es el archivado posterior y tiene su propio camino, con motivo y
    responsable. No sale de «acción siguiente», y por eso hay que pedirlo."""
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    for _ in range(3):
        seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
    seguimiento.close_by_exception(
        trabajo.id, responsible=ACTOR, reason="entregado al cliente")
    cerrado = seguimiento._load(trabajo.id)
    assert cerrado.status is TrackingStatus.CLOSED
    assert seguimiento.next_action_for([trabajo.id], now=ahora())["action"] \
        is NextAction.NONE
    with pytest.raises(InvalidCashDayError):
        seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())


def test_un_trabajo_entregado_no_retrocede_solo(seguimiento, laboratorio):
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
    with pytest.raises(InvalidCashDayError):
        seguimiento._advance(trabajo.id, TrackingStatus.RECEIVED_IN_ASUNCION,
                             responsible=ACTOR)
    assert seguimiento._load(trabajo.id).status \
        is TrackingStatus.RECEIVED_FROM_LABORATORY


def test_volver_al_laboratorio_sigue_permitido_porque_es_un_caso_real(
        seguimiento, laboratorio):
    """Si el trabajo vino mal, vuelve. Es el único retroceso admitido, y esta
    misión no lo toca."""
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
    seguimiento._advance(trabajo.id, TrackingStatus.IN_LABORATORY, responsible=ACTOR)
    assert seguimiento._load(trabajo.id).status is TrackingStatus.IN_LABORATORY


# --------------------------------------------------------------------------
# 10. Persistencia
# --------------------------------------------------------------------------

def test_reiniciar_la_app_conserva_estado_e_historia(ruta, repo, seguimiento,
                                                     laboratorio):
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
    repo.close()
    otro = SQLiteCashDayRepository(ruta)
    try:
        recargado = TrackingService(otro)._load(trabajo.id)
        assert recargado.status is TrackingStatus.RECEIVED_FROM_LABORATORY
        assert len(recargado.transitions) == 3
        # El sello del plazo también sobrevive al reinicio: si sólo viviera en
        # memoria no serviría de evidencia de nada.
        assert "Plazo comprometido" in recargado.transitions[-1].note
        assert "tarde" in recargado.transitions[-1].note
    finally:
        otro.close()


# --------------------------------------------------------------------------
# 13. La pantalla
# --------------------------------------------------------------------------

FUENTE = open("CajaDiaria.py", encoding="utf-8").read()


def test_la_pantalla_habilita_avanzar_sin_mirar_el_atraso():
    """El botón principal se habilita por la acción, no por la condición."""
    bloque = FUENTE[FUENTE.index("def actualizar_acciones_seguimiento"):][:2200]
    assert "info[\"action\"] not in (None, NextAction.NONE)" in bloque
    assert "overdue" not in bloque and "is_overdue" not in bloque, (
        "la barra de acciones volvió a mirar el atraso para decidir")


def test_la_pantalla_ofrece_contactar_como_acompanante_y_no_como_reemplazo():
    bloque = FUENTE[FUENTE.index("def actualizar_acciones_seguimiento"):][:2200]
    assert 'sugerida = info.get("complementary")' in bloque
    assert "Contactar laboratorio" in bloque
    # Contactar renombra el botón de Novedad; nunca toca el botón que avanza.
    contactar = bloque.index("Contactar laboratorio")
    principal = bloque.index("boton_accion_siguiente.configure")
    assert principal < contactar, "contactar no puede reemplazar la acción física"


def test_el_que_llego_a_tiempo_tambien_queda_documentado(seguimiento, laboratorio):
    """El sello no acusa: dice qué plazo regía y si se cumplió. Para el que
    llegó en fecha, deja constancia de que llegó en fecha."""
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=MANANA)
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
    nota = seguimiento._load(trabajo.id).transitions[-1].note
    assert "Plazo comprometido" in nota
    assert "dentro del plazo" in nota and "tarde" not in nota


def test_el_sello_no_pisa_la_nota_que_escribio_la_operadora(seguimiento, laboratorio):
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora(),
                                  note="vino con la montura rayada")
    nota = seguimiento._load(trabajo.id).transitions[-1].note
    assert nota.startswith("vino con la montura rayada")
    assert "Plazo comprometido" in nota


def test_las_transiciones_fuera_del_laboratorio_no_llevan_sello(seguimiento,
                                                                laboratorio):
    """Sólo la salida del laboratorio cierra un plazo. Recibir en Asunción o
    llegar a Pilar no tienen plazo que sellar, y su nota queda limpia."""
    trabajo = seguimiento.register_pilar_batch(
        [{"envelope": "3009", "customer_name": "Lucia"}],
        consultation_date=HOY, created_by=ACTOR)[0]
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
    assert seguimiento._load(trabajo.id).transitions[-1].note == ""


def test_volver_al_laboratorio_no_sella_nada_todavia(seguimiento, laboratorio):
    """Al volver, el trabajo entra a un plazo nuevo. Lo que se sella es la
    salida, y ya se selló cuando llegó."""
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
    seguimiento._advance(trabajo.id, TrackingStatus.IN_LABORATORY, responsible=ACTOR)
    vuelto = seguimiento._load(trabajo.id)
    assert vuelto.status is TrackingStatus.IN_LABORATORY
    assert "Plazo comprometido" not in vuelto.transitions[-1].note
    assert "Plazo comprometido" in vuelto.transitions[-2].note, "el anterior sigue"


def test_la_ficha_del_trabajo_deja_ver_que_llego_tarde(seguimiento, laboratorio):
    """La evidencia tiene que poder mirarse, no sólo estar guardada. «Última
    novedad» es donde la operadora la lee."""
    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
    novedad = seguimiento._load(trabajo.id).last_news()
    assert "RECIBIDO_DEL_LABORATORIO" in novedad
    assert "Plazo comprometido" in novedad and "tarde" in novedad


def test_una_novedad_registrada_a_mano_sigue_teniendo_prioridad(seguimiento,
                                                                laboratorio):
    """Si alguien llamó al laboratorio, eso es lo último que pasó y sigue
    ganándole al sello: esta misión no cambia esa prioridad."""
    from modulos.caja_diaria.domain.tracking import ContactChannel

    trabajo = _en_laboratorio(seguimiento, laboratorio, vence=AYER)
    seguimiento.apply_next_action([trabajo.id], responsible=ACTOR, now=ahora())
    seguimiento.register_contact(
        trabajo.id, operator="ana", channel=ContactChannel.CALL,
        result="Avisamos que llegó")
    assert "Avisamos que llegó" in seguimiento._load(trabajo.id).last_news()
