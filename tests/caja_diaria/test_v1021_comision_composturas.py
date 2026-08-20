# -*- coding: utf-8 -*-
"""V1-021: administrar, leer y explicar la comisión de compostura.

La V1-020 dejó el motor: llegar a LISTO devenga, un hecho paga una sola vez, y
anular compensa en vez de borrar. Lo que no dejó fue cómo se administra eso ni
cómo se lee, y sobre todo no dejó forma de que la tarifa tenga historia.

Estas pruebas cubren cuatro cosas que se sostienen entre sí. Que la política sea
de una persona real del catálogo y sólo la cambie una administradora. Que subir
una tarifa no reescriba lo que ya se devengó, porque cada asiento guarda su
importe *y* la versión que lo explicaba. Que anular compense y que el neto
cierre. Y la que da sentido a las tres: que configurar, devengar o compensar una
comisión no mueva una unidad de inventario, no genere un solo movimiento de caja
y no toque la comisión comercial del 1%, que ni siquiera vive en esta base.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from modulos.caja_diaria.application.admin_ops import (
    ROL_OPERADOR,
    AdminOperations,
)
from modulos.caja_diaria.application.service_jobs import ServiceJobsService
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from tests.migration_chain import afirmar_cadena_completa_con

CLAVE_SOL = "administradora-2026"
CLAVE_LETI = "operadora-leti-2026"

COMISION = 5_000
COMISION_NUEVA = 7_000

RAIZ = Path(__file__).resolve().parents[2]
MIGRACION_032 = (RAIZ / "modulos" / "caja_diaria" / "infrastructure" /
                 "migrations" / "032_comision_composturas.sql")


# ==========================================================================
# Escenario
# ==========================================================================

@pytest.fixture()
def repo(tmp_path):
    repositorio = SQLiteCashDayRepository(tmp_path / "bc_caja.sqlite3")
    repositorio.bind_register_to_branch("PC", "ASUNCION", assigned_by="admin")
    repositorio.bind_register_to_branch("P2", "PILAR", assigned_by="admin")
    yield repositorio
    repositorio.close()


@pytest.fixture()
def admin(repo, tmp_path):
    return AdminOperations(repo, tmp_path / "datos")


@pytest.fixture()
def sol(admin):
    """Quien administra. Es la única que puede tocar una tarifa."""
    return admin.create_initial_admin("sol", CLAVE_SOL)


@pytest.fixture()
def leti(admin, sol):
    """La operadora que atiende el mostrador. No administra política."""
    return admin.create_user(sol.token, username="leti", display_name="Leti",
                             role=ROL_OPERADOR, branch="ASUNCION",
                             password=CLAVE_LETI)


@pytest.fixture()
def rita(admin, sol):
    """Quien hace las composturas y cobra por hacerlas."""
    return admin.create_user(sol.token, username="rita", display_name="Rita",
                             role=ROL_OPERADOR, branch="ASUNCION")


@pytest.fixture()
def direccion(admin, sol):
    """Quien dirige la óptica: también hace trabajos, y no comisiona."""
    return admin.create_user(sol.token, username="direccion",
                             display_name="Dirección", role=ROL_OPERADOR)


@pytest.fixture()
def servicio(repo, admin):
    return ServiceJobsService(repo, admin_ops=admin)


@pytest.fixture()
def con_politica(servicio, sol, rita):
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION,
                              job_type="COMPOSTURA")
    return rita


def nuevo(servicio, **extras):
    datos = dict(customer_name="Sra. López", description="Soldar el frente",
                 job_type="COMPOSTURA", actor="Leti", branch="ASUNCION")
    datos.update(extras)
    return servicio.crear_trabajo(**datos)


def terminado(servicio, **extras):
    """Un trabajo que llegó a LISTO, que es el único que devenga."""
    trabajo = nuevo(servicio, **extras)
    return servicio.marcar_listo(trabajo.id, actor="Rita")


def auditoria(repo, action=None):
    consulta = "SELECT * FROM admin_audit_log"
    parametros = ()
    if action:
        consulta += " WHERE action = ?"
        parametros = (action,)
    with repo._connection() as conexion:
        return [dict(fila) for fila in conexion.execute(consulta, parametros)]


def conteos(repo, tablas):
    with repo._connection() as conexion:
        return {tabla: conexion.execute(
            f"SELECT COUNT(*) FROM {tabla}").fetchone()[0] for tabla in tablas}


# ==========================================================================
# Migración
# ==========================================================================

def test_la_032_se_aplica_y_la_cadena_queda_entera(repo):
    with repo._connection() as conexion:
        afirmar_cadena_completa_con(conexion, "032")


def test_la_politica_vieja_de_una_sola_fila_ya_no_existe(repo):
    """La 031 guardaba la política en una fila que se pisaba.

    Dejarla habría dado dos lugares donde dice cuánto cobra una persona, y
    ningún criterio para decidir cuál manda el día que discrepen.
    """
    with repo._connection() as conexion:
        assert conexion.execute(
            "SELECT name FROM sqlite_master WHERE name='service_commission_policy'"
        ).fetchone() is None


def test_la_032_no_toca_ventas_ni_stock_ni_caja():
    """Se verifica leyendo el .sql, no confiando en él.

    Lo único que la migración altera es la tabla de política -que es
    configuración, no historia económica- y una columna nueva en los asientos.
    """
    # Se miran las sentencias y no el texto suelto: un comentario que menciona
    # `stock_movements` para explicar de dónde se copió una idea no toca nada.
    sql = "\n".join(
        linea for linea in MIGRACION_032.read_text(encoding="utf-8").upper().splitlines()
        if not linea.strip().startswith("--"))
    for prohibida in ("CASH_ENTRIES", "CASH_DAYS", "STOCK_MOVEMENTS", "ARTICLES",
                      "SALE_ITEMS", "ORDERS", "INVENTORY"):
        assert prohibida not in sql, f"la 032 nombra {prohibida}"
    assert "DROP TABLE IF EXISTS SERVICE_COMMISSION_POLICY;" in sql
    # La única tabla que se altera es la de asientos, y sólo para agregarle una
    # columna: la historia económica que ya existe no se reescribe.
    assert sql.count("ALTER TABLE") == 1
    assert "ALTER TABLE SERVICE_JOB_COMMISSIONS\n    ADD COLUMN POLICY_ID" in sql


def test_lo_que_la_031_habia_cargado_se_conserva_como_primera_version(tmp_path):
    """Una base de Casa que ya tenía política cargada no la pierde.

    Se corta la cadena en la 031, se carga una política con la forma vieja y
    recién ahí se deja correr la 032, que es exactamente el orden en el que esto
    pasa en una base real.
    """
    import sqlite3

    ruta = tmp_path / "vieja.sqlite3"
    directorio = MIGRACION_032.parent
    conexion = sqlite3.connect(ruta)
    conexion.row_factory = sqlite3.Row
    for archivo in sorted(directorio.glob("*.sql")):
        if archivo.name.startswith("032"):
            continue
        conexion.executescript(archivo.read_text(encoding="utf-8"))
        # Se deja registrada igual que lo haría el repositorio: si no, al abrir
        # la base éste vuelve a correr toda la cadena desde la 001.
        conexion.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at)"
            " VALUES(?, datetime('now'))", (archivo.name.split("_", 1)[0],))
    conexion.execute(
        "INSERT INTO admin_users(id,username,display_name,password_hash,salt,"
        "iterations,role,active,created_at,updated_at)"
        " VALUES('u-rita','rita','Rita','x','y',200000,'OPERADOR',1,?,?)",
        ("2026-01-01T00:00:00+00:00",) * 2)
    conexion.execute(
        "INSERT INTO service_commission_policy(user_id,job_type,amount,updated_by,"
        "updated_at) VALUES('u-rita','COMPOSTURA',5000,'sol','2026-01-02T00:00:00+00:00')")
    conexion.commit()
    conexion.close()

    repositorio = SQLiteCashDayRepository(ruta)
    try:
        with repositorio._connection() as conexion:
            afirmar_cadena_completa_con(conexion, "032")
            versiones = [dict(fila) for fila in conexion.execute(
                "SELECT * FROM service_commission_policy_versions")]
        assert len(versiones) == 1
        assert versiones[0]["amount"] == 5000
        assert versiones[0]["user_id"] == "u-rita"
        assert versiones[0]["job_type"] == "COMPOSTURA"
        assert versiones[0]["active"] == 1
        assert versiones[0]["created_by"] == "sol"
        # Y sigue siendo la que rige: migrar no puede dejar a nadie sin tarifa.
        vigente = repositorio.service_commission_policy_vigente(
            user_id="u-rita", job_type="COMPOSTURA")
        assert vigente is not None and vigente["amount"] == 5000
    finally:
        repositorio.close()


def test_una_version_de_politica_no_se_reescribe_ni_se_borra(repo, servicio, sol, rita):
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION)
    with repo._connection() as conexion:
        with pytest.raises(Exception):
            conexion.execute(
                "UPDATE service_commission_policy_versions SET amount = 1")
        with pytest.raises(Exception):
            conexion.execute("DELETE FROM service_commission_policy_versions")


# ==========================================================================
# Política: quién puede
# ==========================================================================

def test_una_operadora_no_puede_definir_una_comision(servicio, admin, leti, rita):
    """El rol lo hace cumplir el servicio, no la pantalla.

    Leti entra con su credencial real -no se simula nada- y aun teniendo sesión
    administrativa el rol la frena, porque tener sesión y ser administradora
    dejaron de ser lo mismo en la V1-019B.
    """
    sesion = admin.authenticate("leti", CLAVE_LETI)
    with pytest.raises(InvalidCashDayError):
        servicio.definir_comision(token=sesion.token, user_id=rita.id, amount=COMISION)
    assert not servicio.repository.service_commission_policy_history(user_id=rita.id)


def test_el_intento_denegado_queda_en_la_bitacora(repo, servicio, admin, leti, rita):
    sesion = admin.authenticate("leti", CLAVE_LETI)
    with pytest.raises(InvalidCashDayError):
        servicio.definir_comision(token=sesion.token, user_id=rita.id, amount=COMISION)
    negados = auditoria(repo, "ADMIN_DENIED")
    assert negados and negados[-1]["actor"] == "leti"


def test_sin_sesion_no_se_administra_la_politica(servicio, rita):
    """No alcanza con decir un nombre: eso dejaría la política sin puerta."""
    with pytest.raises(InvalidCashDayError):
        servicio.definir_comision(user_id=rita.id, amount=COMISION, updated_by="sol")


def test_una_operadora_no_puede_leer_el_reporte_completo(servicio, admin, leti):
    sesion = admin.authenticate("leti", CLAVE_LETI)
    with pytest.raises(InvalidCashDayError):
        servicio.reporte_de_comisiones(token=sesion.token)
    with pytest.raises(InvalidCashDayError):
        servicio.politicas_de_comision(token=sesion.token)


# ==========================================================================
# Política: qué se puede definir
# ==========================================================================

def test_definir_una_comision_deja_persona_importe_actor_y_fecha(servicio, sol, rita):
    politica = servicio.definir_comision(
        token=sol.token, user_id=rita.id, amount=COMISION, job_type="COMPOSTURA")
    assert politica["user_id"] == rita.id
    assert politica["amount"] == COMISION
    assert politica["active"] == 1
    assert politica["created_by"] == "sol"
    assert politica["effective_from"] and politica["created_at"]
    assert politica["previous_amount"] is None


def test_la_politica_se_guarda_contra_el_identificador_y_no_contra_el_nombre(
        servicio, admin, sol, rita):
    """Corregir cómo se escribe un nombre no puede mover una tarifa de lugar."""
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION)
    admin.update_user(sol.token, rita.id, display_name="Rita Benítez")
    vigente = servicio.politica_vigente_de(user_id=rita.id, job_type="COMPOSTURA")
    assert vigente is not None and vigente["amount"] == COMISION
    # Y el panel la muestra con el nombre nuevo, sin haber reescrito la fila.
    [fila] = servicio.politicas_de_comision(token=sol.token, user_id=rita.id)
    assert fila["display_name"] == "Rita Benítez"


def test_no_se_le_puede_definir_comision_a_alguien_que_no_existe(servicio, sol):
    with pytest.raises(InvalidCashDayError):
        servicio.definir_comision(token=sol.token, user_id="no-existe", amount=COMISION)


def test_no_se_le_puede_definir_comision_nueva_a_alguien_inactivo(
        servicio, admin, sol, rita):
    admin.set_user_active(sol.token, rita.id, False)
    with pytest.raises(InvalidCashDayError):
        servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION)


def test_una_comision_negativa_no_se_puede_cargar(servicio, sol, rita):
    with pytest.raises(InvalidCashDayError):
        servicio.definir_comision(token=sol.token, user_id=rita.id, amount=-1)


def test_cero_es_una_politica_valida_y_distinta_de_no_tener_ninguna(
        servicio, sol, rita, direccion):
    """«Le corresponde cero» es una respuesta; «no hay política» es una pregunta.

    Las dos terminan en un trabajo que no devenga, y por eso hay que poder
    distinguirlas: una está decidida y la otra está pendiente.
    """
    servicio.definir_comision(token=sol.token, user_id=direccion.id, amount=0)
    decidida = servicio.politica_vigente_de(user_id=direccion.id, job_type="COMPOSTURA")
    assert decidida is not None and decidida["amount"] == 0
    assert servicio.politica_vigente_de(user_id=rita.id, job_type="COMPOSTURA") is None


def test_cambiar_una_comision_pide_motivo_y_la_primera_carga_no(servicio, sol, rita):
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION)
    with pytest.raises(InvalidCashDayError):
        servicio.definir_comision(token=sol.token, user_id=rita.id,
                                  amount=COMISION_NUEVA)
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION_NUEVA,
                              reason="Aumento acordado en agosto")
    assert servicio.comision_de(user_id=rita.id, job_type="COMPOSTURA") == COMISION_NUEVA


def test_cambiar_agrega_una_version_y_guarda_el_importe_anterior(servicio, sol, rita):
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION)
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION_NUEVA,
                              reason="Aumento acordado")
    historial = servicio.historial_de_comision(token=sol.token, user_id=rita.id)
    assert len(historial) == 2
    ultima = historial[0]
    assert ultima["amount"] == COMISION_NUEVA
    assert ultima["previous_amount"] == COMISION
    assert ultima["reason"] == "Aumento acordado"
    assert ultima["supersedes_id"] == historial[1]["id"]


def test_una_politica_con_fecha_futura_todavia_no_rige(servicio, sol, rita):
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION)
    manana = date.today() + timedelta(days=30)
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION_NUEVA,
                              effective_from=manana, reason="Desde el mes que viene")
    assert servicio.comision_de(user_id=rita.id, job_type="COMPOSTURA") == COMISION
    despues = datetime.now(timezone.utc) + timedelta(days=45)
    assert servicio.comision_de(user_id=rita.id, job_type="COMPOSTURA",
                                at=despues) == COMISION_NUEVA


def test_desactivar_una_politica_no_la_borra_y_deja_de_devengar(
        repo, servicio, sol, rita):
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION)
    servicio.desactivar_comision(token=sol.token, user_id=rita.id,
                                 reason="Pasa a sueldo fijo")
    assert servicio.politica_vigente_de(user_id=rita.id, job_type="COMPOSTURA") is None
    historial = servicio.historial_de_comision(token=sol.token, user_id=rita.id)
    assert len(historial) == 2 and historial[0]["active"] == 0
    # El importe se arrastra: dar de baja no puede tocar cuánto valía.
    assert historial[0]["amount"] == COMISION
    trabajo = terminado(servicio, responsible="Rita")
    assert servicio.comisiones_del_trabajo(trabajo.id) == []


def test_volver_a_activar_recupera_el_importe_que_tenia(servicio, sol, rita):
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION)
    servicio.desactivar_comision(token=sol.token, user_id=rita.id, reason="Licencia")
    servicio.activar_comision(token=sol.token, user_id=rita.id, reason="Volvió")
    assert servicio.comision_de(user_id=rita.id, job_type="COMPOSTURA") == COMISION


def test_activar_o_desactivar_pide_motivo(servicio, sol, rita):
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION)
    with pytest.raises(InvalidCashDayError):
        servicio.desactivar_comision(token=sol.token, user_id=rita.id, reason="  ")


def test_no_se_puede_desactivar_una_politica_que_no_existe(servicio, sol, rita):
    with pytest.raises(InvalidCashDayError):
        servicio.desactivar_comision(token=sol.token, user_id=rita.id, reason="x")


def test_la_regla_mas_especifica_gana_y_la_sucursal_es_opcional(servicio, sol, rita):
    """Una política global alcanza; la de sucursal existe si el negocio la pide."""
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=3_000)
    assert servicio.comision_de(user_id=rita.id, job_type="COMPOSTURA",
                                branch="PILAR") == 3_000
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION,
                              branch="PILAR")
    assert servicio.comision_de(user_id=rita.id, job_type="COMPOSTURA",
                                branch="PILAR") == COMISION
    assert servicio.comision_de(user_id=rita.id, job_type="COMPOSTURA",
                                branch="ASUNCION") == 3_000


def test_desactivar_la_excepcion_de_sucursal_devuelve_la_regla_general(
        servicio, sol, rita):
    """Apagar una excepción la apaga a ella, no a la persona."""
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=3_000)
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION,
                              branch="PILAR")
    servicio.desactivar_comision(token=sol.token, user_id=rita.id, branch="PILAR",
                                 reason="Se unifica la tarifa")
    assert servicio.comision_de(user_id=rita.id, job_type="COMPOSTURA",
                                branch="PILAR") == 3_000


# ==========================================================================
# Devengo
# ==========================================================================

def test_un_trabajo_terminado_devenga_la_comision_de_su_responsable(
        servicio, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    [asiento] = servicio.comisiones_del_trabajo(trabajo.id)
    assert asiento["kind"] == "DEVENGO"
    assert asiento["amount"] == COMISION
    assert asiento["beneficiary"] == "Rita"
    assert asiento["user_id"] == con_politica.id


def test_el_asiento_guarda_la_version_de_politica_que_lo_explico(
        servicio, sol, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    [asiento] = servicio.comisiones_del_trabajo(trabajo.id)
    [version] = servicio.historial_de_comision(token=sol.token,
                                               user_id=con_politica.id)
    assert asiento["policy_id"] == version["id"]


def test_sin_politica_no_se_inventa_comision_ni_deuda(servicio, rita):
    trabajo = terminado(servicio, responsible="Rita")
    assert servicio.comisiones_del_trabajo(trabajo.id) == []
    assert servicio.saldo_de_comisiones() == []


def test_la_ausencia_de_politica_queda_visible_en_la_bitacora(repo, servicio, rita):
    trabajo = terminado(servicio, responsible="Rita")
    omitidos = auditoria(repo, "COMMISSION_SKIPPED")
    assert len(omitidos) == 1
    assert omitidos[0]["result"] == "SIN_POLITICA"
    detalle = json.loads(omitidos[0]["details_json"])
    assert detalle["trabajo"] == trabajo.reference
    assert detalle["responsable"] == "Rita"


def test_una_politica_de_cero_no_devenga_pero_se_distingue_del_olvido(
        repo, servicio, sol, direccion):
    servicio.definir_comision(token=sol.token, user_id=direccion.id, amount=0)
    trabajo = terminado(servicio, responsible="Dirección")
    assert servicio.comisiones_del_trabajo(trabajo.id) == []
    omitidos = auditoria(repo, "COMMISSION_SKIPPED")
    assert [fila["result"] for fila in omitidos] == ["IMPORTE_CERO"]


def test_el_devengo_queda_en_la_bitacora_con_su_politica(repo, servicio, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    [linea] = auditoria(repo, "COMMISSION_ACCRUED")
    detalle = json.loads(linea["details_json"])
    assert detalle["importe"] == COMISION
    assert detalle["trabajo"] == trabajo.reference
    assert detalle["politica"]


def test_devenga_igual_por_los_dos_caminos_hasta_listo(servicio, con_politica):
    """RECIBIDO → LISTO y EN_TALLER → LISTO son el mismo hecho económico."""
    directo = terminado(servicio, responsible="Rita")
    otro = nuevo(servicio, responsible="Rita")
    servicio.enviar_a_taller(otro.id, actor="Leti")
    servicio.marcar_listo(otro.id, actor="Rita")
    for trabajo in (directo, otro):
        [asiento] = servicio.comisiones_del_trabajo(trabajo.id)
        assert asiento["amount"] == COMISION


def test_entregar_no_vuelve_a_devengar(servicio, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    servicio.entregar(trabajo.id, actor="Leti", delivered_by="Leti")
    assert len(servicio.comisiones_del_trabajo(trabajo.id)) == 1


def test_marcar_listo_dos_veces_no_paga_dos_veces(servicio, con_politica):
    """El doble click no es un caso raro: es lo que pasa todos los días."""
    trabajo = terminado(servicio, responsible="Rita")
    with pytest.raises(InvalidCashDayError):
        servicio.marcar_listo(trabajo.id, actor="Rita")
    assert len(servicio.comisiones_del_trabajo(trabajo.id)) == 1


def test_reintentar_el_mismo_hecho_no_duplica_el_asiento(repo, servicio, con_politica):
    """Un reintento transaccional repite el INSERT sobre el mismo evento.

    Se ejerce el camino real -volver a guardar el mismo asiento- en vez de
    confiar en que nadie lo va a hacer dos veces.
    """
    trabajo = terminado(servicio, responsible="Rita")
    [asiento] = servicio.comisiones_del_trabajo(trabajo.id)
    repetido = repo.record_service_commission(
        job_id=asiento["job_id"], event_id=asiento["event_id"],
        user_id=asiento["user_id"], beneficiary=asiento["beneficiary"],
        job_type=asiento["job_type"], kind="DEVENGO", amount=asiento["amount"])
    assert repetido is None
    assert len(servicio.comisiones_del_trabajo(trabajo.id)) == 1


def test_rehacer_un_trabajo_devenga_de_nuevo_porque_se_hizo_de_nuevo(
        servicio, con_politica):
    """Reabrir y volver a terminar es un hecho nuevo, y paga como tal.

    Es la contracara de la idempotencia y hay que decir cuál es cuál: no se
    distingue por fecha ni por importe, se distingue porque hay otro evento.
    """
    trabajo = terminado(servicio, responsible="Rita")
    servicio.reabrir(trabajo.id, actor="Leti", reason="Se soltó otra vez")
    servicio.marcar_listo(trabajo.id, actor="Rita")
    asientos = servicio.comisiones_del_trabajo(trabajo.id)
    assert [item["kind"] for item in asientos] == ["DEVENGO", "DEVENGO"]
    assert len({item["event_id"] for item in asientos}) == 2


# ==========================================================================
# Historia: la tarifa de ayer sigue siendo la de ayer
# ==========================================================================

def test_subir_la_tarifa_no_reescribe_lo_que_ya_se_devengo(servicio, sol, con_politica):
    viejo = terminado(servicio, responsible="Rita")
    servicio.definir_comision(token=sol.token, user_id=con_politica.id,
                              amount=COMISION_NUEVA, job_type="COMPOSTURA",
                              reason="Aumento de septiembre")
    nuevo_trabajo = terminado(servicio, responsible="Rita")
    [antes] = servicio.comisiones_del_trabajo(viejo.id)
    [despues] = servicio.comisiones_del_trabajo(nuevo_trabajo.id)
    assert antes["amount"] == COMISION
    assert despues["amount"] == COMISION_NUEVA
    # Y cada uno sigue explicado por la versión que regía cuando devengó.
    assert antes["policy_id"] != despues["policy_id"]


def test_la_politica_de_un_devengo_viejo_se_puede_reconstruir(
        servicio, sol, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    servicio.definir_comision(token=sol.token, user_id=con_politica.id,
                              amount=COMISION_NUEVA, job_type="COMPOSTURA",
                              reason="Aumento")
    resumen = servicio.comision_del_trabajo(trabajo.id)
    [asiento] = resumen["asientos"]
    assert asiento["politica"]["amount"] == COMISION
    assert asiento["importe"] == COMISION


def test_cambiar_el_nombre_visible_no_altera_las_referencias(
        servicio, admin, sol, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    [antes] = servicio.comisiones_del_trabajo(trabajo.id)
    admin.update_user(sol.token, con_politica.id, display_name="Rita Benítez")
    [despues] = servicio.comisiones_del_trabajo(trabajo.id)
    assert despues == antes
    assert despues["user_id"] == con_politica.id


def test_desactivar_a_una_persona_conserva_su_historia_de_comisiones(
        servicio, admin, sol, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    admin.set_user_active(sol.token, con_politica.id, False)
    [asiento] = servicio.comisiones_del_trabajo(trabajo.id)
    assert asiento["amount"] == COMISION
    reporte = servicio.reporte_de_comisiones(token=sol.token,
                                             user_id=con_politica.id)
    assert reporte["totales"]["neto"] == COMISION
    assert servicio.historial_de_comision(token=sol.token, user_id=con_politica.id)


# ==========================================================================
# Compensación
# ==========================================================================

def test_anular_un_trabajo_compensa_en_vez_de_borrar(servicio, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    servicio.anular(trabajo.id, actor="Sol", reason="El cliente no lo trajo nunca")
    asientos = servicio.comisiones_del_trabajo(trabajo.id)
    assert [item["kind"] for item in asientos] == ["DEVENGO", "COMPENSACION"]
    devengo, compensacion = asientos
    assert compensacion["amount"] == -COMISION
    assert compensacion["compensates_id"] == devengo["id"]
    assert "El cliente no lo trajo nunca" in compensacion["note"]


def test_el_neto_despues_de_compensar_es_cero_y_no_desaparece(servicio, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    servicio.anular(trabajo.id, actor="Sol", reason="Se rompió en el taller")
    saldo = {fila["beneficiary"]: fila["amount"] for fila in servicio.saldo_de_comisiones()}
    assert saldo["Rita"] == 0
    resumen = servicio.comision_del_trabajo(trabajo.id)
    assert resumen["neto"] == 0
    assert resumen["asientos"][0]["estado"] == "COMPENSADA"


def test_la_compensacion_hereda_la_politica_del_devengo_que_revierte(
        servicio, sol, con_politica):
    """Revierte aquel hecho, no el precio de hoy."""
    trabajo = terminado(servicio, responsible="Rita")
    servicio.definir_comision(token=sol.token, user_id=con_politica.id,
                              amount=COMISION_NUEVA, job_type="COMPOSTURA",
                              reason="Aumento")
    servicio.anular(trabajo.id, actor="Sol", reason="Anulado")
    devengo, compensacion = servicio.comisiones_del_trabajo(trabajo.id)
    assert compensacion["policy_id"] == devengo["policy_id"]
    assert compensacion["amount"] == -COMISION


def test_un_devengo_no_se_puede_compensar_dos_veces(repo, servicio, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    servicio.anular(trabajo.id, actor="Sol", reason="Anulado")
    devengo, compensacion = servicio.comisiones_del_trabajo(trabajo.id)
    with repo._connection() as conexion:
        with pytest.raises(Exception):
            conexion.execute(
                "INSERT INTO service_job_commissions(id,job_id,event_id,beneficiary,"
                "job_type,kind,amount,compensates_id,created_at)"
                " VALUES('x',?,?,'Rita','COMPOSTURA','COMPENSACION',?,?,?)",
                (trabajo.id, "evento-inventado", -COMISION, devengo["id"],
                 datetime.now(timezone.utc).isoformat()))


def test_un_asiento_de_comision_no_se_borra_ni_se_reescribe(repo, servicio, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    with repo._connection() as conexion:
        with pytest.raises(Exception):
            conexion.execute("UPDATE service_job_commissions SET amount = 1")
        with pytest.raises(Exception):
            conexion.execute("DELETE FROM service_job_commissions")
    assert len(servicio.comisiones_del_trabajo(trabajo.id)) == 1


def test_la_compensacion_queda_en_la_bitacora_con_su_motivo(repo, servicio, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    servicio.anular(trabajo.id, actor="Sol", reason="Se equivocó de trabajo")
    [linea] = auditoria(repo, "COMMISSION_COMPENSATED")
    detalle = json.loads(linea["details_json"])
    assert detalle["motivo"] == "Se equivocó de trabajo"
    assert detalle["importe"] == -COMISION


# ==========================================================================
# Trazabilidad
# ==========================================================================

def test_desde_el_trabajo_se_ve_toda_su_consecuencia_economica(
        servicio, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    resumen = servicio.comision_del_trabajo(trabajo.id)
    assert resumen["genero_comision"] is True
    assert resumen["trabajo"] == trabajo.reference
    [asiento] = resumen["asientos"]
    assert asiento["beneficiario"] == "Rita"
    assert asiento["importe"] == COMISION
    assert asiento["estado"] == "DEVENGADA"
    assert asiento["politica"]["amount"] == COMISION
    assert asiento["evento"]


def test_un_trabajo_que_no_comisiono_lo_dice_en_vez_de_callarse(servicio, rita):
    trabajo = terminado(servicio, responsible="Rita")
    resumen = servicio.comision_del_trabajo(trabajo.id)
    assert resumen["genero_comision"] is False
    assert resumen["asientos"] == []


def test_desde_el_asiento_se_llega_al_trabajo_que_lo_origino(servicio, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    [asiento] = servicio.comisiones_del_trabajo(trabajo.id)
    assert asiento["job_id"] == trabajo.id
    assert servicio.obtener(asiento["job_id"]).reference == trabajo.reference
    # Y el evento que lo causó está en la historia del trabajo, no suelto.
    eventos = {hecho.id for hecho in servicio.historial(trabajo.id)}
    assert asiento["event_id"] in eventos


# ==========================================================================
# Reporte
# ==========================================================================

def test_el_reporte_suma_bruto_compensado_y_neto(servicio, sol, con_politica):
    uno = terminado(servicio, responsible="Rita")
    terminado(servicio, responsible="Rita")
    servicio.anular(uno.id, actor="Sol", reason="Anulado")
    reporte = servicio.reporte_de_comisiones(token=sol.token)
    totales = reporte["totales"]
    assert totales["trabajos"] == 2
    assert totales["bruto"] == COMISION * 2
    assert totales["compensado"] == -COMISION
    assert totales["neto"] == COMISION


def test_los_totales_cuadran_con_las_filas_que_se_muestran(servicio, sol, con_politica):
    for _ in range(3):
        terminado(servicio, responsible="Rita")
    reporte = servicio.reporte_de_comisiones(token=sol.token)
    assert reporte["totales"]["neto"] == sum(
        fila["net_amount"] for fila in reporte["filas"])
    assert reporte["totales"]["trabajos"] == len(reporte["filas"])


def test_el_reporte_filtra_por_sucursal(servicio, sol, con_politica):
    terminado(servicio, responsible="Rita", branch="ASUNCION")
    terminado(servicio, responsible="Rita", branch="PILAR")
    asuncion = servicio.reporte_de_comisiones(token=sol.token, branch="ASUNCION")
    assert asuncion["totales"]["trabajos"] == 1
    assert asuncion["filas"][0]["branch"] == "ASUNCION"


def test_el_reporte_filtra_por_responsable(servicio, sol, con_politica, direccion):
    servicio.definir_comision(token=sol.token, user_id=direccion.id, amount=2_000)
    terminado(servicio, responsible="Rita")
    terminado(servicio, responsible="Dirección")
    reporte = servicio.reporte_de_comisiones(token=sol.token, responsible="Rita")
    assert reporte["totales"]["trabajos"] == 1
    assert reporte["filas"][0]["beneficiary"] == "Rita"


def test_el_reporte_filtra_por_rango_de_fechas(servicio, sol, con_politica):
    terminado(servicio, responsible="Rita")
    ayer = date.today() - timedelta(days=1)
    vacio = servicio.reporte_de_comisiones(
        token=sol.token, date_from=ayer - timedelta(days=5), date_to=ayer)
    assert vacio["totales"]["trabajos"] == 0
    hoy = servicio.reporte_de_comisiones(
        token=sol.token, date_from=date.today(), date_to=date.today())
    assert hoy["totales"]["trabajos"] == 1


def test_el_reporte_filtra_por_estado(servicio, sol, con_politica):
    uno = terminado(servicio, responsible="Rita")
    terminado(servicio, responsible="Rita")
    servicio.anular(uno.id, actor="Sol", reason="Anulado")
    devengadas = servicio.reporte_de_comisiones(token=sol.token, estado="DEVENGADA")
    compensadas = servicio.reporte_de_comisiones(token=sol.token, estado="COMPENSADA")
    assert devengadas["totales"]["trabajos"] == 1
    assert compensadas["totales"]["trabajos"] == 1
    assert compensadas["filas"][0]["net_amount"] == 0


def test_un_estado_desconocido_se_rechaza(servicio, sol):
    with pytest.raises(InvalidCashDayError):
        servicio.reporte_de_comisiones(token=sol.token, estado="LIQUIDADA")


def test_la_fila_del_reporte_trae_lo_que_hace_falta_para_entenderla(
        servicio, sol, con_politica):
    trabajo = terminado(servicio, responsible="Rita")
    [fila] = servicio.reporte_de_comisiones(token=sol.token)["filas"]
    assert fila["reference"] == trabajo.reference
    assert fila["customer"] == "Sra. López"
    assert fila["beneficiary"] == "Rita"
    assert fila["branch"] == "ASUNCION"
    assert fila["accrued_amount"] == COMISION
    assert fila["compensated_amount"] == 0
    assert fila["net_amount"] == COMISION
    assert fila["estado"] == "DEVENGADA"
    assert fila["policy_amount"] == COMISION


def test_los_trabajos_que_no_devengaron_se_listan_aparte(servicio, sol, rita):
    trabajo = terminado(servicio, responsible="Rita")
    reporte = servicio.reporte_de_comisiones(token=sol.token)
    assert reporte["totales"]["sin_politica"] == 1
    assert reporte["sin_politica"][0]["reference"] == trabajo.reference


def test_un_trabajo_que_devengo_no_aparece_como_pendiente(servicio, sol, con_politica):
    terminado(servicio, responsible="Rita")
    reporte = servicio.reporte_de_comisiones(token=sol.token)
    assert reporte["totales"]["sin_politica"] == 0


# ==========================================================================
# Separación: inventario, caja y el 1% comercial
# ==========================================================================

TABLAS_INTOCABLES = ("cash_days", "cash_entries", "cash_counts", "orders",
                     "sale_items", "stock_movements", "articles", "tracked_works",
                     "domain_events")


def test_administrar_una_comision_no_mueve_inventario_ni_caja(
        repo, servicio, sol, rita):
    antes = conteos(repo, TABLAS_INTOCABLES)
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION)
    servicio.definir_comision(token=sol.token, user_id=rita.id, amount=COMISION_NUEVA,
                              reason="Aumento")
    servicio.desactivar_comision(token=sol.token, user_id=rita.id, reason="Baja")
    servicio.activar_comision(token=sol.token, user_id=rita.id, reason="Alta")
    assert conteos(repo, TABLAS_INTOCABLES) == antes


def test_devengar_y_compensar_no_mueven_inventario_ni_caja(
        repo, servicio, sol, con_politica):
    """Nace la comisión, se revierte, y no sale un guaraní de la caja.

    Devengo y pago son dos hechos distintos. Que uno implique el otro sería
    entregar plata que nadie contó.
    """
    antes = conteos(repo, TABLAS_INTOCABLES)
    trabajo = terminado(servicio, responsible="Rita")
    servicio.anular(trabajo.id, actor="Sol", reason="Anulado")
    assert conteos(repo, TABLAS_INTOCABLES) == antes


def test_una_comision_devengada_no_es_un_gasto_ni_una_salida_de_caja(
        repo, servicio, con_politica):
    terminado(servicio, responsible="Rita")
    with repo._connection() as conexion:
        assert conexion.execute(
            "SELECT COUNT(*) FROM cash_entries").fetchone()[0] == 0


def test_la_comision_de_compostura_no_toca_la_comision_comercial(
        servicio, sol, con_politica):
    """El 1% ni siquiera vive en esta base.

    Se calcula en BC Gestión, sobre ventas, en un archivo aparte. No hay tabla
    de la que traerlo por accidente, y esta prueba deja escrito por qué.
    """
    terminado(servicio, responsible="Rita")
    [fila] = servicio.reporte_de_comisiones(token=sol.token)["filas"]
    assert fila["job_type"] == "COMPOSTURA"
    assert fila["accrued_amount"] == COMISION  # importe fijo, no un porcentaje
    with servicio.repository._connection() as conexion:
        tablas = {nombre for (nombre,) in conexion.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    assert not {tabla for tabla in tablas
                if "sales_commission" in tabla or "commercial_commission" in tabla}


def test_el_modulo_de_comision_no_importa_nada_del_nucleo_comercial():
    """La separación es estructural, no una promesa del comentario."""
    for ruta in (RAIZ / "modulos" / "caja_diaria" / "application" / "service_jobs.py",
                 RAIZ / "modulos" / "caja_diaria" / "ui" / "commission_panel.py"):
        texto = ruta.read_text(encoding="utf-8")
        assert "modulos.comercial" not in texto
        assert "stock_movements" not in texto
        assert "inventory" not in texto.lower()
        assert "SobresVenta" not in texto


def test_una_venta_normal_no_genera_comision_de_compostura(repo, servicio, con_politica):
    ahora = datetime.now().isoformat()
    with repo._connection() as conexion:
        conexion.execute(
            "INSERT INTO cash_days(id,business_date,unit,opening_cash,status,opened_at)"
            " VALUES ('dia-1',?,'PC',0,'OPEN',?)", (str(date.today()), ahora))
        conexion.execute(
            "INSERT INTO cash_entries(id,cash_day_id,description,total,created_at,"
            "updated_at) VALUES ('venta-1','dia-1','Lentes recetados',450000,?,?)",
            (ahora, ahora))
        conexion.commit()
    assert servicio.saldo_de_comisiones() == []
    with repo._connection() as conexion:
        assert conexion.execute(
            "SELECT COUNT(*) FROM service_job_commissions").fetchone()[0] == 0


def test_crear_una_compostura_no_genera_ninguna_comision(servicio, con_politica):
    """La comisión es consecuencia de haberlo hecho, no de haberlo escrito."""
    trabajo = nuevo(servicio, responsible="Rita")
    assert servicio.comisiones_del_trabajo(trabajo.id) == []
    servicio.enviar_a_taller(trabajo.id, actor="Leti")
    assert servicio.comisiones_del_trabajo(trabajo.id) == []


# ==========================================================================
# Estados económicos: lo que no se inventa
# ==========================================================================

def test_no_hay_estado_de_liquidacion_porque_todavia_no_hay_pago(repo):
    """Hoy el negocio no registra el pago de la comisión de compostura.

    Inventarle un estado LIQUIDADA sería escribir un flujo que nadie ejecuta, y
    después alguien leería «pagada» donde nunca se pagó. Lo que sí distinguimos
    es lo devengado de lo compensado, que son hechos que ocurren.
    """
    with repo._connection() as conexion:
        (sql,) = conexion.execute(
            "SELECT sql FROM sqlite_master WHERE name='service_job_commissions'"
        ).fetchone()
    assert "'DEVENGO'" in sql and "'COMPENSACION'" in sql
    assert "LIQUIDADA" not in sql.upper() and "PAGADA" not in sql.upper()


# ==========================================================================
# Panel
# ==========================================================================

def test_el_panel_de_comisiones_no_decide_permisos_por_su_cuenta():
    """La pestaña es por dónde se entra, no la cerradura."""
    panel = (RAIZ / "modulos" / "caja_diaria" / "ui" / "commission_panel.py"
             ).read_text(encoding="utf-8")
    # Toda acción viaja con el token y el servicio vuelve a pedir el rol.
    assert panel.count("token=self.token") >= 5
    assert "require_admin" not in panel  # no se re-implementa la regla acá


def test_el_panel_de_comisiones_esta_colgado_del_area_administrativa():
    fuente = (RAIZ / "CajaDiaria.py").read_text(encoding="utf-8")
    admin = fuente.index("def mostrar_panel_administrador(")
    seccion = fuente[admin:admin + 4000]
    assert "Comisiones de composturas" in seccion
    assert "construir_panel_comisiones" in seccion
    assert "token=session.token" in seccion
