# -*- coding: utf-8 -*-
"""V1-020: composturas y trabajos de taller, sin que nada de eso sea inventario.

Lo que la óptica hace todos los días y no estaba en ningún lado: alguien deja
los lentes para que le pongan un tornillo. Hasta hoy eso vivía en un cuaderno.

Estas pruebas cubren tres cosas que se apoyan una en otra. Que un trabajo tenga
origen, responsable, estado, causa y traza. Que la comisión de compostura sea
una consecuencia de haber hecho el trabajo y no de haberlo escrito, y que no se
pueda pagar dos veces. Y sobre todo la que le da nombre al slice: que crear,
mandar al taller, terminar, entregar o anular un trabajo no mueva una sola
unidad de inventario, en ningún estado y por ningún camino.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from modulos.caja_diaria.application.admin_ops import (
    ROL_OPERADOR,
    AdminOperations,
)
from modulos.caja_diaria.application.service_jobs import (
    ServiceJobsService,
    VISTA_ENTREGADOS,
    VISTA_EN_TALLER,
    VISTA_LISTOS,
    VISTA_PENDIENTES,
    VISTA_TODOS,
)
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.service_jobs import (
    ALLOWED_TRANSITIONS,
    ESTADO_DE_DEVENGO,
    JobEvent,
    JobStatus,
    ServiceJob,
    siguiente_referencia,
)
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository
from tests.migration_chain import afirmar_cadena_completa_con

CLAVE_SOL = "administradora-2026"
CLAVE_LETI = "operadora-leti-2026"

COMISION_COMPOSTURA = 5_000


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
    return admin.create_initial_admin("sol", CLAVE_SOL)


@pytest.fixture()
def leti(admin, sol):
    """La operadora que atiende el mostrador."""
    return admin.create_user(sol.token, username="leti", display_name="Leti",
                             role=ROL_OPERADOR, branch="ASUNCION",
                             password=CLAVE_LETI)


@pytest.fixture()
def tallerista(admin, sol):
    """Quien hace las composturas. Existe en el catálogo, como toda persona."""
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
def con_comision(servicio, tallerista, sol):
    """La política de comisión, cargada como la carga la Óptica: a mano.

    V1-021: cargarla pide sesión administrativa. Antes alcanzaba con decir un
    nombre, y eso dejaba la política sin puerta.
    """
    servicio.definir_comision(user_id=tallerista.id, amount=COMISION_COMPOSTURA,
                              job_type="COMPOSTURA", token=sol.token)
    return tallerista


@pytest.fixture()
def cobro(repo):
    """Una venta real en la caja, para vincularla desde un trabajo.

    Se crea acá y no desde el modulo de trabajos justamente porque el trabajo
    no puede crear cobros: solo puede referenciar uno que ya ocurrio.
    """
    from datetime import datetime
    ahora = datetime.now().isoformat()
    with repo._connection() as conexion:
        conexion.execute(
            "INSERT INTO cash_days(id,business_date,unit,opening_cash,status,opened_at)"
            " VALUES ('dia-1',?,'PC',0,'OPEN',?)", (str(date.today()), ahora))
        conexion.execute(
            "INSERT INTO cash_entries(id,cash_day_id,description,total,created_at,updated_at)"
            " VALUES ('cobro-1','dia-1','Compostura',30000,?,?)", (ahora, ahora))
        conexion.commit()
    return "cobro-1"


def nuevo(servicio, **extras):
    datos = dict(customer_name="Sra. López", description="Soldar el frente",
                 job_type="COMPOSTURA", actor="Leti", branch="ASUNCION")
    datos.update(extras)
    return servicio.crear_trabajo(**datos)


def stock(repo):
    """Cuántos movimientos de inventario hay. La cifra que no puede cambiar."""
    with repo._connection() as conexion:
        return conexion.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0]


# ==========================================================================
# Migración
# ==========================================================================

def test_la_031_se_aplica_y_la_cadena_queda_entera(repo):
    with repo._connection() as conexion:
        afirmar_cadena_completa_con(conexion, "031")


def test_la_031_no_toca_ninguna_tabla_existente():
    """Estrictamente aditiva: se verifica leyendo el .sql, no confiando en él."""
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[2] / "modulos" / "caja_diaria" /
           "infrastructure" / "migrations" / "031_trabajos_operativos.sql"
           ).read_text(encoding="utf-8").upper()
    # Se miran las sentencias, no el texto suelto: «BEFORE UPDATE» dentro de un
    # trigger es una regla que impide escribir, no una escritura.
    sentencias = [linea.strip() for linea in sql.splitlines()]
    assert not [linea for linea in sentencias
                if linea.startswith(("ALTER TABLE", "DROP ", "UPDATE ", "DELETE "))]
    # Lo único que escribe es su propio catálogo y su propia versión.
    inserts = [linea for linea in sentencias if linea.startswith("INSERT")]
    assert all("SERVICE_JOB_TYPES" in linea or "SCHEMA_MIGRATIONS" in linea
               for linea in inserts), inserts


def test_ningun_tipo_de_trabajo_puede_declararse_stockeable(repo):
    """El invariante está en el esquema, no solo en el código."""
    import sqlite3
    with repo._connection() as conexion:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute(
                "INSERT INTO service_job_types(code,label,stockeable)"
                " VALUES ('REPUESTO','Repuesto fisico',1)")


# ==========================================================================
# Creación
# ==========================================================================

def test_un_trabajo_simple_se_registra_con_lo_minimo(servicio):
    trabajo = nuevo(servicio)
    assert trabajo.reference == "T-00001"
    assert trabajo.status is JobStatus.RECEIVED
    assert trabajo.branch == "ASUNCION"
    assert trabajo.received_by == "Leti"
    assert trabajo.is_charged is False


def test_una_compostura_lleva_cliente_telefono_y_observacion(servicio):
    trabajo = nuevo(servicio, customer_phone="0981-111222",
                    observations="Armazón de la nieta")
    assert trabajo.customer_phone == "0981-111222"
    assert trabajo.observations == "Armazón de la nieta"


def test_un_trabajo_sin_cliente_no_se_registra(servicio):
    with pytest.raises(InvalidCashDayError):
        nuevo(servicio, customer_name="   ")


def test_un_trabajo_sin_descripcion_no_se_registra(servicio):
    with pytest.raises(InvalidCashDayError):
        nuevo(servicio, description="")


def test_un_tipo_de_trabajo_inventado_se_rechaza(servicio):
    with pytest.raises(InvalidCashDayError):
        nuevo(servicio, job_type="LO_QUE_SEA")


def test_las_referencias_son_correlativas_y_no_se_repiten(servicio):
    referencias = [nuevo(servicio).reference for _ in range(3)]
    assert referencias == ["T-00001", "T-00002", "T-00003"]


def test_la_referencia_sigue_al_mayor_existente():
    """Deriva de lo guardado y no de un contador aparte: sobrevive a un restore."""
    assert siguiente_referencia([]) == "T-00001"
    assert siguiente_referencia(["T-00001", "T-00007", "T-00003"]) == "T-00008"
    assert siguiente_referencia(["basura", "T-XX"]) == "T-00001"


def test_no_hay_operacion_anonima(servicio):
    with pytest.raises(InvalidCashDayError):
        servicio.crear_trabajo(customer_name="X", description="Y", branch="ASUNCION")


# ==========================================================================
# Responsables: el catálogo real, no una lista aparte
# ==========================================================================

def test_el_responsable_sale_del_catalogo_de_personas(servicio, tallerista):
    trabajo = nuevo(servicio, responsible="Rita")
    assert trabajo.responsible == "Rita"
    assert trabajo.responsible_user_id == tallerista.id


def test_una_persona_que_no_existe_no_puede_ser_responsable(servicio):
    with pytest.raises(InvalidCashDayError):
        nuevo(servicio, responsible="Alguien Que No Existe")


def test_una_persona_inactiva_no_puede_quedar_de_responsable(
        servicio, admin, sol, tallerista):
    admin.set_user_active(sol.token, tallerista.id, False)
    with pytest.raises(InvalidCashDayError):
        nuevo(servicio, responsible="Rita")


def test_cambiar_de_responsable_queda_en_la_historia(servicio, tallerista, direccion):
    trabajo = nuevo(servicio, responsible="Rita")
    trabajo = servicio.asignar_responsable(trabajo.id, "Dirección", actor="Leti")
    assert trabajo.responsible == "Dirección"
    assert trabajo.responsible_user_id == direccion.id
    tipos = [hecho.event_type for hecho in servicio.historial(trabajo.id)]
    assert JobEvent.RESPONSIBLE_ASSIGNED in tipos
    assert JobEvent.RESPONSIBLE_CHANGED in tipos


def test_los_responsables_disponibles_son_los_activos(servicio, tallerista, leti):
    disponibles = list(servicio.responsables_disponibles())
    assert "Rita" in disponibles and "Leti" in disponibles


# ==========================================================================
# Estados
# ==========================================================================

def test_el_flujo_completo_avanza(servicio):
    trabajo = nuevo(servicio)
    trabajo = servicio.enviar_a_taller(trabajo.id, actor="Leti")
    assert trabajo.status is JobStatus.IN_WORKSHOP
    trabajo = servicio.marcar_listo(trabajo.id, actor="Rita")
    assert trabajo.status is JobStatus.READY
    assert trabajo.ready_at is not None
    assert trabajo.workshop_return_at is not None
    trabajo = servicio.entregar(trabajo.id, actor="Leti")
    assert trabajo.status is JobStatus.DELIVERED
    assert trabajo.delivered_at is not None
    assert trabajo.delivered_by == "Leti"


def test_un_trabajo_de_mostrador_puede_ir_directo_a_listo(servicio):
    """Un tornillo se pone en dos minutos y no pasa por ningún taller."""
    trabajo = nuevo(servicio, job_type="TORNILLO")
    trabajo = servicio.marcar_listo(trabajo.id, actor="Leti")
    assert trabajo.status is JobStatus.READY


def test_entregar_sin_pasar_por_listo_no_se_puede(servicio):
    trabajo = nuevo(servicio)
    with pytest.raises(InvalidCashDayError):
        servicio.entregar(trabajo.id, actor="Leti")


def test_un_trabajo_anulado_no_avanza_mas(servicio):
    trabajo = nuevo(servicio)
    trabajo = servicio.anular(trabajo.id, reason="El cliente se llevó el armazón",
                              actor="Leti")
    assert trabajo.status is JobStatus.VOIDED
    for destino in (JobStatus.RECEIVED, JobStatus.IN_WORKSHOP, JobStatus.READY,
                    JobStatus.DELIVERED):
        with pytest.raises(InvalidCashDayError):
            servicio.cambiar_estado(trabajo.id, destino, actor="Leti", reason="x")


def test_anular_exige_motivo(servicio):
    trabajo = nuevo(servicio)
    with pytest.raises(InvalidCashDayError):
        servicio.anular(trabajo.id, reason="   ", actor="Leti")


def test_reabrir_un_entregado_exige_motivo_explicito(servicio):
    trabajo = nuevo(servicio)
    servicio.marcar_listo(trabajo.id, actor="Leti")
    servicio.entregar(trabajo.id, actor="Leti")
    with pytest.raises(InvalidCashDayError):
        servicio.cambiar_estado(trabajo.id, JobStatus.IN_WORKSHOP, actor="Leti")
    reabierto = servicio.reabrir(trabajo.id, reason="Volvió flojo el tornillo",
                                 actor="Leti")
    assert reabierto.status is JobStatus.IN_WORKSHOP


def test_reabrir_se_registra_como_reapertura_y_no_como_envio(servicio):
    """La diferencia importa: cuántos hubo que rehacer no es cuántos fueron."""
    trabajo = nuevo(servicio)
    servicio.marcar_listo(trabajo.id, actor="Leti")
    servicio.reabrir(trabajo.id, reason="Vino mal", actor="Leti")
    tipos = [hecho.event_type for hecho in servicio.historial(trabajo.id)]
    assert JobEvent.REOPENED in tipos
    assert JobEvent.SENT_TO_WORKSHOP not in tipos


def test_no_se_puede_transicionar_al_mismo_estado(servicio):
    trabajo = nuevo(servicio)
    with pytest.raises(InvalidCashDayError):
        servicio.cambiar_estado(trabajo.id, JobStatus.RECEIVED, actor="Leti")


def test_las_transiciones_declaradas_cubren_todos_los_estados():
    """Un estado sin entrada en la tabla explotaría recién en producción."""
    assert set(ALLOWED_TRANSITIONS) == set(JobStatus)
    assert ALLOWED_TRANSITIONS[JobStatus.VOIDED] == ()


# ==========================================================================
# Sucursal
# ==========================================================================

def test_la_sucursal_la_decide_la_caja_y_no_la_persona(servicio, admin, leti):
    """V1-019B ya es la autoridad sobre esto; acá se comprueba que se respeta."""
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    trabajo = servicio.crear_trabajo(
        customer_name="Sr. Ruiz", description="Cambiar plaqueta",
        job_type="PLAQUETA", token=sesion.token, host_branch="PILAR")
    # Leti figura en Asunción, pero esta caja atiende en Pilar.
    assert trabajo.branch == "PILAR"
    assert trabajo.received_by == "Leti"


def test_una_sucursal_desconocida_se_rechaza(servicio):
    with pytest.raises(InvalidCashDayError):
        nuevo(servicio, branch="ENCARNACION")


def test_los_trabajos_de_cada_sucursal_no_se_mezclan(servicio):
    nuevo(servicio, branch="ASUNCION")
    nuevo(servicio, branch="PILAR", customer_name="Sr. Ruiz")
    asuncion = servicio.tablero(vista=VISTA_TODOS, branch="ASUNCION")
    pilar = servicio.tablero(vista=VISTA_TODOS, branch="PILAR")
    assert [fila.customer for fila in asuncion] == ["Sra. López"]
    assert [fila.customer for fila in pilar] == ["Sr. Ruiz"]


# ==========================================================================
# Comisión de composturas
# ==========================================================================

def test_un_responsable_con_politica_devenga_al_quedar_listo(servicio, con_comision):
    trabajo = nuevo(servicio, responsible="Rita")
    assert servicio.comisiones_del_trabajo(trabajo.id) == []
    servicio.enviar_a_taller(trabajo.id, actor="Leti")
    assert servicio.comisiones_del_trabajo(trabajo.id) == []
    servicio.marcar_listo(trabajo.id, actor="Rita")
    asientos = servicio.comisiones_del_trabajo(trabajo.id)
    assert [(a["kind"], a["amount"]) for a in asientos] == [
        ("DEVENGO", COMISION_COMPOSTURA)]


def test_el_devengo_es_al_quedar_listo_y_no_al_entregar(servicio, con_comision):
    """Se paga el trabajo hecho, no que el cliente pase a retirarlo."""
    assert ESTADO_DE_DEVENGO is JobStatus.READY
    trabajo = nuevo(servicio, responsible="Rita")
    servicio.marcar_listo(trabajo.id, actor="Rita")
    antes = servicio.comisiones_del_trabajo(trabajo.id)
    servicio.entregar(trabajo.id, actor="Leti")
    assert servicio.comisiones_del_trabajo(trabajo.id) == antes


def test_un_responsable_sin_politica_no_comisiona(servicio, direccion):
    trabajo = nuevo(servicio, responsible="Dirección")
    servicio.marcar_listo(trabajo.id, actor="Dirección")
    assert servicio.comisiones_del_trabajo(trabajo.id) == []


def test_un_trabajo_sin_responsable_no_comisiona(servicio, con_comision):
    trabajo = nuevo(servicio)
    servicio.marcar_listo(trabajo.id, actor="Leti")
    assert servicio.comisiones_del_trabajo(trabajo.id) == []


def test_la_politica_por_tipo_gana_sobre_la_general(servicio, tallerista, sol):
    servicio.definir_comision(user_id=tallerista.id, amount=3_000, token=sol.token)
    servicio.definir_comision(user_id=tallerista.id, amount=COMISION_COMPOSTURA,
                              job_type="COMPOSTURA", token=sol.token)
    assert servicio.comision_de(user_id=tallerista.id,
                                job_type="COMPOSTURA") == COMISION_COMPOSTURA
    assert servicio.comision_de(user_id=tallerista.id, job_type="HILO") == 3_000


def test_una_comision_negativa_no_se_puede_cargar(servicio, tallerista, sol):
    with pytest.raises(InvalidCashDayError):
        servicio.definir_comision(user_id=tallerista.id, amount=-1, token=sol.token)


def test_la_comision_no_se_duplica_aunque_se_reintente(servicio, con_comision):
    """El asiento cuelga de un hecho, y un hecho paga una sola vez."""
    trabajo = nuevo(servicio, responsible="Rita")
    trabajo = servicio.marcar_listo(trabajo.id, actor="Rita")
    hecho = [h for h in trabajo.history
             if h.event_type is JobEvent.COMMISSION_ACCRUED][0]
    repetido = servicio.repository.record_service_commission(
        job_id=trabajo.id, event_id=hecho.id, user_id=None, beneficiary="Rita",
        job_type="COMPOSTURA", kind="DEVENGO", amount=COMISION_COMPOSTURA)
    assert repetido is None
    assert len(servicio.comisiones_del_trabajo(trabajo.id)) == 1


def test_anular_compensa_la_comision_sin_borrarla(servicio, con_comision):
    trabajo = nuevo(servicio, responsible="Rita")
    servicio.marcar_listo(trabajo.id, actor="Rita")
    servicio.anular(trabajo.id, reason="El cliente no volvió nunca", actor="Leti")
    asientos = servicio.comisiones_del_trabajo(trabajo.id)
    assert [a["kind"] for a in asientos] == ["DEVENGO", "COMPENSACION"]
    assert sum(a["amount"] for a in asientos) == 0
    saldo = {fila["beneficiary"]: fila["amount"] for fila in servicio.saldo_de_comisiones()}
    assert saldo["Rita"] == 0


def test_una_comision_ya_compensada_no_se_compensa_de_nuevo(servicio, con_comision):
    trabajo = nuevo(servicio, responsible="Rita")
    servicio.marcar_listo(trabajo.id, actor="Rita")
    servicio.anular(trabajo.id, reason="Anulado", actor="Leti")
    asientos = servicio.comisiones_del_trabajo(trabajo.id)
    # Un segundo intento de anular ya no puede: el trabajo está anulado.
    with pytest.raises(InvalidCashDayError):
        servicio.anular(trabajo.id, reason="Otra vez", actor="Leti")
    assert servicio.comisiones_del_trabajo(trabajo.id) == asientos


def test_rehacer_un_trabajo_devenga_de_nuevo(servicio, con_comision):
    """Si volvió al taller y se hizo otra vez, se hizo otra vez."""
    trabajo = nuevo(servicio, responsible="Rita")
    servicio.marcar_listo(trabajo.id, actor="Rita")
    servicio.reabrir(trabajo.id, reason="Vino flojo", actor="Leti")
    servicio.marcar_listo(trabajo.id, actor="Rita")
    asientos = servicio.comisiones_del_trabajo(trabajo.id)
    assert [a["kind"] for a in asientos] == ["DEVENGO", "DEVENGO"]
    assert sum(a["amount"] for a in asientos) == 2 * COMISION_COMPOSTURA


def test_la_comision_de_compostura_no_toca_la_comision_comercial(servicio, con_comision):
    """Son dos cosas y viven en dos lados: acá no hay ni un dato de venta."""
    trabajo = nuevo(servicio, responsible="Rita")
    servicio.marcar_listo(trabajo.id, actor="Rita")
    asiento = servicio.comisiones_del_trabajo(trabajo.id)[0]
    assert asiento["job_type"] == "COMPOSTURA"
    assert "cash_entry_id" not in asiento
    with servicio.repository._connection() as conexion:
        # Ninguna venta se tocó al devengar.
        assert conexion.execute("SELECT COUNT(*) FROM cash_entries").fetchone()[0] == 0


def test_la_comision_es_append_only(servicio, con_comision):
    import sqlite3
    trabajo = nuevo(servicio, responsible="Rita")
    servicio.marcar_listo(trabajo.id, actor="Rita")
    with servicio.repository._connection() as conexion:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("UPDATE service_job_commissions SET amount = 1")
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("DELETE FROM service_job_commissions")


# ==========================================================================
# Caja: el trabajo referencia el cobro, no lo crea
# ==========================================================================

def test_un_trabajo_puede_estar_listo_y_sin_cobrar(servicio):
    trabajo = nuevo(servicio)
    trabajo = servicio.marcar_listo(trabajo.id, actor="Leti")
    assert trabajo.status is JobStatus.READY
    assert trabajo.is_charged is False


def test_vincular_un_cobro_no_crea_movimiento_de_caja(servicio, repo, cobro):
    trabajo = nuevo(servicio)
    with repo._connection() as conexion:
        antes = conexion.execute("SELECT COUNT(*) FROM cash_entries").fetchone()[0]
    trabajo = servicio.vincular_cobro(trabajo.id, cobro, amount=30_000, actor="Leti")
    with repo._connection() as conexion:
        despues = conexion.execute("SELECT COUNT(*) FROM cash_entries").fetchone()[0]
    assert antes == despues == 1
    assert trabajo.is_charged is True
    assert trabajo.charged_amount == 30_000


def test_un_cobro_que_no_existe_en_la_caja_no_se_puede_referenciar(servicio):
    """No hay cobro sin hecho: la referencia tiene que apuntar a una venta real."""
    import sqlite3
    trabajo = nuevo(servicio)
    with pytest.raises(sqlite3.IntegrityError):
        servicio.vincular_cobro(trabajo.id, "no-existe", amount=30_000, actor="Leti")


def test_un_trabajo_cobrado_puede_seguir_sin_entregar(servicio, cobro):
    trabajo = nuevo(servicio)
    trabajo = servicio.vincular_cobro(trabajo.id, cobro, amount=30_000, actor="Leti")
    assert trabajo.status is JobStatus.RECEIVED
    assert trabajo.is_charged is True


def test_no_se_vincula_un_segundo_cobro_distinto(servicio, cobro):
    trabajo = nuevo(servicio)
    servicio.vincular_cobro(trabajo.id, cobro, amount=30_000, actor="Leti")
    with pytest.raises(InvalidCashDayError):
        servicio.vincular_cobro(trabajo.id, "cobro-2", amount=30_000, actor="Leti")


# ==========================================================================
# INVENTARIO: el invariante crítico del slice
# ==========================================================================

@pytest.mark.parametrize("concepto", ["HILO", "TORNILLO", "PLAQUETA", "COMPOSTURA"])
def test_ningun_estado_de_ningun_concepto_mueve_inventario(servicio, repo, concepto,
                                                           con_comision):
    """Hilo, Tornillo, Plaqueta y Compostura no generan stock. En ningún estado.

    Se recorre el ciclo entero y se cuentan los movimientos después de cada
    paso, no solo al final: un movimiento que se creara y se revirtiera también
    sería un movimiento.
    """
    assert stock(repo) == 0
    trabajo = nuevo(servicio, job_type=concepto, responsible="Rita")
    assert stock(repo) == 0, "crear movió inventario"
    servicio.enviar_a_taller(trabajo.id, actor="Leti")
    assert stock(repo) == 0, "enviar a taller movió inventario"
    servicio.marcar_listo(trabajo.id, actor="Rita")
    assert stock(repo) == 0, "marcar listo movió inventario"
    servicio.entregar(trabajo.id, actor="Leti")
    assert stock(repo) == 0, "entregar movió inventario"

    otro = nuevo(servicio, job_type=concepto, responsible="Rita")
    servicio.anular(otro.id, reason="Prueba de anulación", actor="Leti")
    assert stock(repo) == 0, "anular movió inventario"


def test_tampoco_se_crean_articulos_ni_hechos_de_dominio(servicio, repo):
    """Ni inventario, ni artículos ficticios, ni eventos del núcleo comercial."""
    trabajo = nuevo(servicio, job_type="HILO", responsible="")
    servicio.marcar_listo(trabajo.id, actor="Leti")
    servicio.entregar(trabajo.id, actor="Leti")
    with repo._connection() as conexion:
        assert conexion.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM domain_events").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM event_effects").fetchone()[0] == 0


def test_el_modulo_de_trabajos_no_conoce_al_nucleo_comercial():
    """No puede mover stock porque no sabe quién lo mueve.

    Es más fuerte que contar movimientos: aunque alguien escriba mañana un
    camino nuevo, este módulo no tiene con qué tocar inventario.
    """
    from pathlib import Path
    raiz = Path(__file__).resolve().parents[2] / "modulos" / "caja_diaria"
    for ruta in (raiz / "domain" / "service_jobs.py",
                 raiz / "application" / "service_jobs.py",
                 raiz / "ui" / "service_jobs_panel.py"):
        texto = ruta.read_text(encoding="utf-8")
        assert "modulos.comercial" not in texto
        assert "stock_movements" not in texto
        assert "inventory" not in texto.lower()


def test_los_conceptos_de_servicio_siguen_siendo_no_stockeables():
    """V1-010 los corrigió con su evidencia. Esto verifica que sigue vigente.

    No se vuelve a corregir nada acá: se comprueba que la decisión tomada
    aguas arriba no se deshizo, que es lo que un slice nuevo puede romper sin
    darse cuenta.
    """
    from pathlib import Path
    herramienta = (Path(__file__).resolve().parents[2] / "tools" /
                   "conciliacion_inventario_corregido_optica.py"
                   ).read_text(encoding="utf-8")
    assert "A_SERVICIO" in herramienta
    for sku in ("2000070", "2000071", "2000072", "2000056"):
        assert sku in herramienta
    assert "SERVICIO_NO_STOCKEABLE" in herramienta


# ==========================================================================
# Invariantes económicas del resto del sistema
# ==========================================================================

def test_el_ciclo_completo_no_toca_ninguna_estructura_economica(servicio, repo,
                                                               con_comision):
    """Antes y después: ventas, caja, arqueos, pedidos, stock y seguimiento."""
    tablas = ("cash_days", "cash_entries", "cash_counts", "orders", "sale_items",
              "stock_movements", "articles", "tracked_works", "domain_events")

    def foto():
        with repo._connection() as conexion:
            return {tabla: conexion.execute(
                f"SELECT COUNT(*) FROM {tabla}").fetchone()[0] for tabla in tablas}

    antes = foto()
    trabajo = nuevo(servicio, responsible="Rita")
    servicio.enviar_a_taller(trabajo.id, actor="Leti")
    servicio.marcar_listo(trabajo.id, actor="Rita")
    servicio.entregar(trabajo.id, actor="Leti")
    otro = nuevo(servicio, responsible="Rita")
    servicio.marcar_listo(otro.id, actor="Rita")
    servicio.anular(otro.id, reason="Anulado en la prueba", actor="Leti")
    assert foto() == antes


# ==========================================================================
# Auditoría e irreversibilidad
# ==========================================================================

def test_cada_paso_deja_su_hecho_con_actor_y_estados(servicio):
    trabajo = nuevo(servicio)
    servicio.enviar_a_taller(trabajo.id, actor="Leti")
    servicio.marcar_listo(trabajo.id, actor="Rita")
    hechos = servicio.historial(trabajo.id)
    assert [h.event_type for h in hechos] == [
        JobEvent.CREATED, JobEvent.SENT_TO_WORKSHOP, JobEvent.MARKED_READY]
    envio = hechos[1]
    assert envio.actor == "Leti"
    assert envio.from_status is JobStatus.RECEIVED
    assert envio.to_status is JobStatus.IN_WORKSHOP
    assert envio.occurred_at is not None


def test_el_motivo_queda_guardado_donde_se_exigio(servicio):
    trabajo = nuevo(servicio)
    servicio.anular(trabajo.id, reason="El cliente retiró el armazón", actor="Leti")
    anulacion = [h for h in servicio.historial(trabajo.id)
                 if h.event_type is JobEvent.VOIDED][0]
    assert anulacion.reason == "El cliente retiró el armazón"


def test_editar_datos_deja_dicho_que_cambio(servicio):
    trabajo = nuevo(servicio)
    trabajo = servicio.actualizar_datos(trabajo.id, actor="Leti",
                                        customer_phone="0985-333444")
    cambio = [h for h in servicio.historial(trabajo.id)
              if h.event_type is JobEvent.DATA_CHANGED][0]
    assert cambio.detail["despues"]["customer_phone"] == "0985-333444"


def test_un_trabajo_anulado_conserva_toda_su_historia(servicio):
    trabajo = nuevo(servicio)
    servicio.enviar_a_taller(trabajo.id, actor="Leti")
    servicio.anular(trabajo.id, reason="Se perdió el armazón", actor="Leti")
    hechos = servicio.historial(trabajo.id)
    assert JobEvent.SENT_TO_WORKSHOP in [h.event_type for h in hechos]
    assert servicio.obtener(trabajo.id).voided_at is not None


def test_no_hay_hard_delete_de_un_trabajo(servicio, repo):
    import sqlite3
    trabajo = nuevo(servicio)
    with repo._connection() as conexion:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("DELETE FROM service_jobs WHERE id = ?", (trabajo.id,))


def test_la_historia_no_se_reescribe_ni_se_borra(servicio, repo):
    import sqlite3
    trabajo = nuevo(servicio)
    with repo._connection() as conexion:
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("UPDATE service_job_events SET actor = 'otro'")
        with pytest.raises(sqlite3.IntegrityError):
            conexion.execute("DELETE FROM service_job_events")


def test_guardar_dos_veces_no_duplica_la_historia(servicio, repo):
    """Reabrir la ventana o recuperarse de un corte no puede duplicar hechos."""
    trabajo = nuevo(servicio)
    repo.save_service_job(trabajo)
    repo.save_service_job(trabajo)
    assert len(servicio.historial(trabajo.id)) == len(trabajo.history)


# ==========================================================================
# Identidad de sesión
# ==========================================================================

def test_lo_que_hace_la_operadora_queda_a_su_nombre(servicio, admin, leti):
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    trabajo = servicio.crear_trabajo(
        customer_name="Sra. Duarte", description="Ajustar patilla",
        job_type="AJUSTE", token=sesion.token, host_branch="ASUNCION")
    assert trabajo.received_by == "Leti"
    assert servicio.historial(trabajo.id)[0].actor == "Leti"


def test_un_token_invalido_no_registra_nada(servicio):
    with pytest.raises(InvalidCashDayError):
        servicio.crear_trabajo(customer_name="X", description="Y",
                               token="token-falso", host_branch="ASUNCION")


# ==========================================================================
# Vistas del tablero
# ==========================================================================

def test_los_listos_para_entregar_se_encuentran_solos(servicio):
    listo = nuevo(servicio, customer_name="Listo")
    servicio.marcar_listo(listo.id, actor="Leti")
    nuevo(servicio, customer_name="Recién recibido")
    en_taller = nuevo(servicio, customer_name="En taller")
    servicio.enviar_a_taller(en_taller.id, actor="Leti")

    assert [f.customer for f in servicio.tablero(vista=VISTA_LISTOS)] == ["Listo"]
    assert [f.customer for f in servicio.tablero(vista=VISTA_EN_TALLER)] == ["En taller"]
    pendientes = {f.customer for f in servicio.tablero(vista=VISTA_PENDIENTES)}
    assert pendientes == {"Listo", "Recién recibido", "En taller"}


def test_los_entregados_salen_de_los_pendientes(servicio):
    trabajo = nuevo(servicio)
    servicio.marcar_listo(trabajo.id, actor="Leti")
    servicio.entregar(trabajo.id, actor="Leti")
    assert servicio.tablero(vista=VISTA_PENDIENTES) == []
    assert len(servicio.tablero(vista=VISTA_ENTREGADOS)) == 1


def test_se_puede_filtrar_por_responsable(servicio, tallerista, direccion):
    de_rita = nuevo(servicio, responsible="Rita", customer_name="De Rita")
    nuevo(servicio, responsible="Dirección", customer_name="De Dirección")
    filas = servicio.tablero(vista=VISTA_TODOS, responsible="Rita")
    assert [f.customer for f in filas] == ["De Rita"]


def test_se_puede_filtrar_por_fecha(servicio):
    nuevo(servicio)
    hoy = date.today()
    assert len(servicio.tablero(vista=VISTA_TODOS, received_from=hoy,
                                received_to=hoy)) == 1
    ayer = hoy - timedelta(days=1)
    assert servicio.tablero(vista=VISTA_TODOS, received_from=ayer,
                            received_to=ayer) == []


def test_una_vista_inventada_se_rechaza(servicio):
    with pytest.raises(InvalidCashDayError):
        servicio.tablero(vista="LO_QUE_SEA")


def test_el_resumen_cuenta_cada_estado(servicio):
    trabajo = nuevo(servicio)
    servicio.marcar_listo(trabajo.id, actor="Leti")
    nuevo(servicio)
    resumen = servicio.resumen()
    assert resumen["LISTO"] == 1
    assert resumen["RECIBIDO"] == 1
    assert resumen["ENTREGADO"] == 0


def test_la_fila_dice_el_estado_economico_aparte_del_operativo(servicio, cobro):
    trabajo = nuevo(servicio)
    fila = servicio.tablero(vista=VISTA_PENDIENTES)[0]
    assert fila.charge_label == ""
    servicio.vincular_cobro(trabajo.id, cobro, amount=30_000, actor="Leti")
    fila = servicio.tablero(vista=VISTA_PENDIENTES)[0]
    assert fila.charge_label.startswith("COBRADO")
    assert fila.status_label == "RECIBIDO"


def test_un_trabajo_sin_responsable_se_ve_sin_asignar(servicio):
    nuevo(servicio)
    assert servicio.tablero(vista=VISTA_PENDIENTES)[0].responsible == "SIN ASIGNAR"


# ==========================================================================
# Persistencia
# ==========================================================================

def test_el_trabajo_sobrevive_a_releerlo_entero(servicio, repo, con_comision):
    trabajo = nuevo(servicio, responsible="Rita", customer_phone="0981-1",
                    observations="Cuidado con el frente",
                    promised_date=date.today() + timedelta(days=2))
    servicio.enviar_a_taller(trabajo.id, actor="Leti")
    servicio.marcar_listo(trabajo.id, actor="Rita")
    leido = repo.get_service_job(trabajo.id)
    assert leido.customer_phone == "0981-1"
    assert leido.observations == "Cuidado con el frente"
    assert leido.promised_date == date.today() + timedelta(days=2)
    assert leido.responsible == "Rita"
    assert leido.status is JobStatus.READY
    assert len(leido.history) == 5


def test_se_encuentra_por_numero(servicio, repo):
    trabajo = nuevo(servicio)
    assert repo.get_service_job_by_reference(trabajo.reference).id == trabajo.id


def test_un_trabajo_que_no_existe_se_dice(servicio):
    with pytest.raises(InvalidCashDayError):
        servicio.obtener("no-existe")


# ==========================================================================
# Lo que encontro la revision
# ==========================================================================

def test_el_trabajo_y_su_comision_se_guardan_juntos(servicio, repo, con_comision):
    """Si el asiento no puede escribirse, el trabajo tampoco queda listo.

    Antes iban en dos transacciones seguidas: un corte en el medio dejaba un
    trabajo que decia haber devengado y una comision que no existia.
    """
    import sqlite3
    trabajo = nuevo(servicio, responsible="Rita")
    original = repo._insertar_comision

    def romper(conexion, asiento):
        raise sqlite3.IntegrityError("falla simulada al asentar la comision")

    repo._insertar_comision = romper
    try:
        with pytest.raises(sqlite3.IntegrityError):
            servicio.marcar_listo(trabajo.id, actor="Rita")
    finally:
        repo._insertar_comision = original

    # Ni el trabajo avanzo, ni quedo el hecho de devengo colgando.
    releido = servicio.obtener(trabajo.id)
    assert releido.status is JobStatus.RECEIVED
    assert JobEvent.COMMISSION_ACCRUED not in [h.event_type for h in releido.history]
    assert servicio.comisiones_del_trabajo(trabajo.id) == []


def test_se_pueden_ver_los_trabajos_de_una_persona_que_ya_no_esta(
        servicio, admin, sol, tallerista):
    """Dar de baja a alguien no borra lo que hizo, y tiene que poder mirarse."""
    trabajo = nuevo(servicio, responsible="Rita")
    admin.set_user_active(sol.token, tallerista.id, False)
    filas = servicio.tablero(vista=VISTA_TODOS, responsible="Rita")
    assert [f.id for f in filas] == [trabajo.id]
    # Pero sigue sin poder quedar de responsable de un trabajo nuevo.
    with pytest.raises(InvalidCashDayError):
        nuevo(servicio, responsible="Rita")


def test_editar_a_un_tipo_de_trabajo_inventado_se_rechaza_con_un_mensaje(servicio):
    """No se deja llegar a la clave foranea: el error de la base no le sirve a nadie."""
    trabajo = nuevo(servicio)
    with pytest.raises(InvalidCashDayError):
        servicio.actualizar_datos(trabajo.id, actor="Leti", job_type="REPUESTO")


def test_editar_a_un_tipo_valido_se_registra(servicio):
    trabajo = nuevo(servicio)
    trabajo = servicio.actualizar_datos(trabajo.id, actor="Leti", job_type="HILO")
    assert trabajo.job_type == "HILO"


def test_los_responsables_se_ordenan_por_el_nombre_que_se_ve(repo, servicio, admin, sol):
    """Sin nombre visible, la persona se lista por su usuario y en su lugar.

    `create_user` no deja crear a alguien sin nombre visible: si viene vacío lo
    reemplaza por el usuario. Así que esta fila se escribe por SQL, que es el
    único camino por el que hoy puede aparecer —una importación, una migración,
    una corrección a mano— y es exactamente el caso en que las dos consultas que
    listan personas dejaban de coincidir entre sí.
    """
    admin.create_user(sol.token, username="ana", display_name="Ana", role=ROL_OPERADOR)
    admin.create_user(sol.token, username="zoe", display_name="Zoe", role=ROL_OPERADOR)
    with repo._connection() as conexion:
        conexion.execute("UPDATE admin_users SET display_name='   ' WHERE username='zoe'")
        conexion.commit()
    disponibles = list(servicio.responsables_disponibles())
    assert "zoe" in disponibles, "sin nombre visible tiene que listarse por su usuario"
    # Ordenado por lo que se ve: 'Ana' antes que 'zoe', y no 'zoe' al principio
    # por tener la columna cruda vacía.
    assert disponibles.index("Ana") < disponibles.index("zoe")
    assert disponibles == sorted(disponibles, key=str.lower)
