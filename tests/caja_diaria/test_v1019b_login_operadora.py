# -*- coding: utf-8 -*-
"""V1-019B: quién está operando la caja, de verdad y durante toda la jornada.

V1-019A dejó el catálogo de personas con sus roles. Lo que faltaba era que
abrir BC Caja significara que alguien entró: hasta ahora quien operaba salía de
una variable de entorno, y por eso todo lo que se registraba decía «Operadora».

Lo que más se prueba acá son dos cosas que se contradicen sólo en apariencia:
que la sesión dure la jornada entera —pedir la contraseña cada veinte minutos
termina con la contraseña anotada al lado de la pantalla— y que aun así lo
sensible siga exigiendo identificarse de nuevo.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timedelta

import pytest

from modulos.caja_diaria.application.admin_ops import (
    ROL_ADMIN,
    ROL_OPERADOR,
    AdminOperations,
)
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import CashDay, CashEntry
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

CLAVE_SOL = "administradora-2026"
CLAVE_LETI = "operadora-leti-2026"


@pytest.fixture()
def ruta(tmp_path):
    return tmp_path / "bc_caja.sqlite3"


@pytest.fixture()
def repo(ruta):
    repositorio = SQLiteCashDayRepository(ruta)
    repositorio.bind_register_to_branch("PC", "ASUNCION", assigned_by="admin")
    repositorio.bind_register_to_branch("P2", "PILAR", assigned_by="admin")
    yield repositorio
    repositorio.close()


@pytest.fixture()
def admin(repo, tmp_path):
    return AdminOperations(repo, tmp_path / "datos")


@pytest.fixture()
def sol(admin):
    """La administradora, que es como arranca cualquier instalación."""
    return admin.create_initial_admin("sol", CLAVE_SOL)


@pytest.fixture()
def leti(admin, sol):
    """Una operadora con credencial: atiende, y no administra."""
    return admin.create_user(sol.token, username="leti", display_name="Leti",
                             role=ROL_OPERADOR, branch="ASUNCION",
                             password=CLAVE_LETI)


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------

def test_una_operadora_entra_a_la_caja(admin, leti):
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    assert sesion.username == "leti"
    assert sesion.display_name == "Leti"
    assert sesion.role == ROL_OPERADOR
    assert sesion.branch == "ASUNCION"
    assert sesion.user_id == leti.id
    assert sesion.is_admin is False


def test_una_administradora_tambien_puede_atender(admin, sol):
    sesion = admin.authenticate_operator("sol", CLAVE_SOL)
    assert sesion.role == ROL_ADMIN
    assert sesion.is_admin is True


def test_la_contrasena_incorrecta_no_entra(admin, leti):
    with pytest.raises(InvalidCashDayError):
        admin.authenticate_operator("leti", "la-que-no-es")


def test_un_usuario_inexistente_no_entra(admin, sol):
    with pytest.raises(InvalidCashDayError):
        admin.authenticate_operator("nadie", CLAVE_LETI)


def test_una_persona_sin_contrasena_no_entra(admin, sol):
    """Existe para ser nombrada en una venta y para tener rol. No para entrar."""
    admin.create_user(sol.token, username="rosa", display_name="Rosa",
                      role=ROL_OPERADOR)
    with pytest.raises(InvalidCashDayError):
        admin.authenticate_operator("rosa", "")
    with pytest.raises(InvalidCashDayError):
        admin.authenticate_operator("rosa", "cualquier-cosa-larga")


def test_una_persona_desactivada_no_entra(admin, sol, leti):
    admin.set_user_active(sol.token, leti.id, False)
    with pytest.raises(InvalidCashDayError):
        admin.authenticate_operator("leti", CLAVE_LETI)


def test_el_bloqueo_exponencial_sigue_vigente(admin, leti):
    """No se construyó autenticación nueva: la que había ya se defendía sola."""
    for _ in range(3):
        with pytest.raises(InvalidCashDayError):
            admin.authenticate_operator("leti", "incorrecta")
    # Ahora ni siquiera la buena entra: quedó bloqueada un rato.
    with pytest.raises(InvalidCashDayError):
        admin.authenticate_operator("leti", CLAVE_LETI)


def test_el_login_de_caja_queda_auditado(admin, leti):
    admin.authenticate_operator("leti", CLAVE_LETI)
    sesion_admin = admin.authenticate("sol", CLAVE_SOL)
    acciones = [f["action"] for f in admin.audit_rows(sesion_admin.token, limit=200)]
    assert "CASH_LOGIN_SUCCESS" in acciones


def test_entrar_a_atender_no_deja_abierta_una_sesion_administrativa(admin, sol):
    """Si la dejara, una administradora que atiende tendría el panel abierto
    toda la tarde sin volver a identificarse."""
    antes = set(admin._sessions)
    sesion_caja = admin.authenticate_operator("sol", CLAVE_SOL)
    assert set(admin._sessions) == antes, (
        "entrar a atender dejó abierta una sesión que autoriza cosas sensibles")
    with pytest.raises(InvalidCashDayError):
        admin.list_users(sesion_caja.token)


# --------------------------------------------------------------------------
# Duración, expiración y logout
# --------------------------------------------------------------------------

def test_la_sesion_dura_la_jornada_y_no_veinte_minutos(admin, leti):
    """La administrativa vence a los 20 minutos porque protege cosas que se
    hacen una vez. Ésta acompaña a alguien que atiende ocho horas."""
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    duracion = sesion.expires_at - sesion.started_at
    assert duracion > timedelta(minutes=20)
    assert sesion.expires_at.hour == 0 and sesion.expires_at.minute == 0
    assert sesion.expires_at.date() == sesion.started_at.date() + timedelta(days=1)


def test_la_sesion_no_sobrevive_a_la_noche(admin, leti):
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    vencida = replace(sesion, expires_at=datetime.now().astimezone() - timedelta(minutes=1))
    admin._cash_sessions[sesion.token] = vencida
    with pytest.raises(InvalidCashDayError, match="venció"):
        admin.require_operator(sesion.token)


def test_una_sesion_vencida_queda_registrada(admin, leti, sol):
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    admin._cash_sessions[sesion.token] = replace(
        sesion, expires_at=datetime.now().astimezone() - timedelta(minutes=1))
    with pytest.raises(InvalidCashDayError):
        admin.require_operator(sesion.token)
    acciones = [f["action"] for f in admin.audit_rows(
        admin.authenticate("sol", CLAVE_SOL).token, limit=200)]
    assert "CASH_SESSION_EXPIRED" in acciones


def test_desactivar_a_alguien_la_saca_de_la_caja_aunque_ya_estuviera_adentro(
        admin, sol, leti):
    """Se pregunta a la base en cada uso, no sólo al entrar."""
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    assert admin.require_operator(sesion.token).username == "leti"
    admin.set_user_active(sol.token, leti.id, False)
    with pytest.raises(InvalidCashDayError, match="ya no está activa"):
        admin.require_operator(sesion.token)


def test_logout(admin, leti, sol):
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    admin.logout_operator(sesion.token, reason="fin de turno")
    with pytest.raises(InvalidCashDayError):
        admin.require_operator(sesion.token)
    acciones = [f["action"] for f in admin.audit_rows(
        admin.authenticate("sol", CLAVE_SOL).token, limit=200)]
    assert "CASH_LOGOUT" in acciones


def test_un_token_inventado_no_sirve(admin, leti):
    with pytest.raises(InvalidCashDayError):
        admin.require_operator("token-escrito-a-mano")


def test_el_token_viejo_no_se_puede_reusar_despues_del_logout(admin, leti):
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    viejo = sesion.token
    admin.logout_operator(viejo)
    nueva = admin.authenticate_operator("leti", CLAVE_LETI)
    assert nueva.token != viejo
    with pytest.raises(InvalidCashDayError):
        admin.require_operator(viejo)


# --------------------------------------------------------------------------
# Cambio de operadora
# --------------------------------------------------------------------------

def test_cambiar_de_operadora_a_media_tarde(admin, sol, leti):
    primera = admin.authenticate_operator("leti", CLAVE_LETI)
    segunda = admin.switch_operator(primera.token, "sol", CLAVE_SOL)
    assert segunda.username == "sol"
    with pytest.raises(InvalidCashDayError):
        admin.require_operator(primera.token), "la sesión anterior tiene que morir"


def test_el_relevo_queda_registrado_con_quien_salio_y_quien_entro(admin, sol, leti):
    primera = admin.authenticate_operator("leti", CLAVE_LETI)
    admin.switch_operator(primera.token, "sol", CLAVE_SOL)
    filas = admin.audit_rows(admin.authenticate("sol", CLAVE_SOL).token, limit=200)
    relevo = [f for f in filas if f["action"] == "CASH_OPERATOR_CHANGED"][0]
    assert "leti" in relevo["details_json"] and "sol" in relevo["details_json"]
    assert relevo["recorded_at"]


def test_cambiar_de_operadora_no_toca_la_caja_del_dia(repo, admin, sol, leti):
    """El arqueo es de la caja y de la sucursal, no de quien está adelante."""
    repo.save(CashDay(business_date=date(2026, 8, 19), unit="PC", opening_cash=100000,
                      opened_by="Leti",
                      entries=(CashEntry(description="Maria", envelope="1001",
                                         total=450000, cash=450000,
                                         saleswoman="Leti"),)))
    antes = repo.get_by_date_and_unit(date(2026, 8, 19), "PC")
    primera = admin.authenticate_operator("leti", CLAVE_LETI)
    admin.switch_operator(primera.token, "sol", CLAVE_SOL)
    despues = repo.get_by_date_and_unit(date(2026, 8, 19), "PC")
    assert despues.totals() == antes.totals()
    assert despues.status == antes.status
    assert [e.saleswoman for e in despues.entries] == ["Leti"]


def test_un_relevo_fallido_no_saca_a_la_que_estaba(admin, leti):
    primera = admin.authenticate_operator("leti", CLAVE_LETI)
    with pytest.raises(InvalidCashDayError):
        admin.switch_operator(primera.token, "sol", "clave-equivocada")
    assert admin.require_operator(primera.token).username == "leti"


# --------------------------------------------------------------------------
# Permisos
# --------------------------------------------------------------------------

def test_una_operadora_opera_la_caja(admin, leti):
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    assert admin.require_operator(sesion.token).display_name == "Leti"


@pytest.mark.parametrize("accion", [
    lambda a, t: a.list_users(t),
    lambda a, t: a.create_user(t, username="nueva", display_name="Nueva"),
    lambda a, t: a.audit_rows(t),
    lambda a, t: a.update_setting(t, "branch", {"branch": "X", "cashbox": "Y"}),
    lambda a, t: a.set_mail_secret(t, "secreto"),
])
def test_la_sesion_de_caja_no_autoriza_nada_administrativo(admin, leti, accion):
    """Ni siquiera la de una administradora: son tokens de mundos distintos.

    Se llama al servicio directamente, sin pantalla de por medio, porque
    esconder un botón no es un permiso."""
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    with pytest.raises(InvalidCashDayError):
        accion(admin, sesion.token)


def test_una_administradora_que_atiende_tampoco_administra_con_ese_token(admin, sol):
    """Para lo sensible se vuelve a identificar. Ésa es la reautenticación."""
    caja = admin.authenticate_operator("sol", CLAVE_SOL)
    with pytest.raises(InvalidCashDayError):
        admin.list_users(caja.token)
    panel = admin.authenticate("sol", CLAVE_SOL)
    assert admin.list_users(panel.token) is not None


def test_la_administradora_conserva_acceso_completo_por_su_camino(admin, sol):
    assert admin.list_users(sol.token) is not None
    assert admin.audit_rows(sol.token) is not None


def test_una_operadora_no_consigue_una_sesion_administrativa(admin, leti):
    """Entrar al panel con credencial de operadora da sesión, pero no permisos.
    El rol viaja en la sesión y `require_admin` lo mira."""
    panel = admin.authenticate("leti", CLAVE_LETI)
    assert panel.role == ROL_OPERADOR
    with pytest.raises(InvalidCashDayError):
        admin.list_users(panel.token)


# --------------------------------------------------------------------------
# Vendedora
# --------------------------------------------------------------------------

def test_la_vendedora_por_defecto_es_quien_esta_operando(admin, leti):
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    assert sesion.display_name == "Leti"
    assert sesion.display_name in admin.active_salespeople()


def test_se_puede_registrar_que_vendio_otra_y_queda_auditado(admin, sol, leti):
    """Pasa de verdad: una administrativa carga la venta que hizo otra chica."""
    admin.create_user(sol.token, username="rosa", display_name="Rosa",
                      role=ROL_OPERADOR)
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    admin.audit_saleswoman_override(sesion.token, "Rosa", envelope="1001")
    filas = admin.audit_rows(admin.authenticate("sol", CLAVE_SOL).token, limit=200)
    override = [f for f in filas if f["action"] == "SALESWOMAN_OVERRIDE"][0]
    assert "Leti" in override["details_json"] and "Rosa" in override["details_json"]


def test_elegir_a_la_misma_persona_no_genera_ruido(admin, leti, sol):
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    admin.audit_saleswoman_override(sesion.token, "Leti", envelope="1001")
    filas = admin.audit_rows(admin.authenticate("sol", CLAVE_SOL).token, limit=200)
    assert not [f for f in filas if f["action"] == "SALESWOMAN_OVERRIDE"]


def test_cambiar_el_nombre_de_una_persona_no_reescribe_sus_ventas(repo, admin, sol,
                                                                  leti):
    repo.save(CashDay(business_date=date(2026, 8, 19), unit="PC", opening_cash=0,
                      opened_by="Leti",
                      entries=(CashEntry(description="Maria", envelope="1001",
                                         total=450000, cash=450000,
                                         saleswoman="Leti"),)))
    admin.update_user(sol.token, leti.id, display_name="Leticia Ramírez")
    dia = repo.get_by_date_and_unit(date(2026, 8, 19), "PC")
    assert dia.entries[0].saleswoman == "Leti"


def test_la_vendedora_sigue_sin_ser_foreign_key(repo):
    with repo._connection() as con:
        claves = con.execute("PRAGMA foreign_key_list(cash_entries)").fetchall()
    assert not [f for f in claves if f[2] == "admin_users"]


# --------------------------------------------------------------------------
# Sucursal
# --------------------------------------------------------------------------

def test_la_sucursal_efectiva_es_la_de_la_caja(admin, leti, repo):
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    contexto = admin.effective_branch(
        sesion.token, repo.branch_of_register("PC"))
    assert contexto["branch"] == "ASUNCION"
    assert contexto["mismatch"] is False


def test_una_discrepancia_de_sucursal_se_avisa_y_no_se_corrige_sola(admin, leti,
                                                                    repo):
    """Leti figura en Asunción y está operando la caja de Pilar. Cuál de los dos
    datos está mal no lo puede decidir el sistema."""
    sesion = admin.authenticate_operator("leti", CLAVE_LETI)
    contexto = admin.effective_branch(sesion.token, repo.branch_of_register("P2"))
    assert contexto["mismatch"] is True
    assert contexto["branch"] == "PILAR", "manda la caja, no la persona"
    assert contexto["user_branch"] == "ASUNCION"
    assert "Leti" in contexto["aviso"]


def test_una_persona_sin_sucursal_no_genera_discrepancia(admin, sol, repo):
    """Quien administra suele no tener sucursal fija, y eso no es un conflicto."""
    sesion = admin.authenticate_operator("sol", CLAVE_SOL)
    contexto = admin.effective_branch(sesion.token, repo.branch_of_register("PC"))
    assert contexto["mismatch"] is False
    assert contexto["branch"] == "ASUNCION"


# --------------------------------------------------------------------------
# Integridad: autenticar no puede mover un guaraní
# --------------------------------------------------------------------------

def test_todo_el_ciclo_de_sesiones_no_toca_nada_economico(repo, admin, sol, leti):
    repo.save(CashDay(business_date=date(2026, 8, 19), unit="PC", opening_cash=100000,
                      opened_by="Leti",
                      entries=(CashEntry(description="Maria", envelope="1001",
                                         total=450000, cash=450000,
                                         saleswoman="Leti"),
                               CashEntry(description="Nafta", expenses=50000))))

    def foto():
        with repo._connection() as con:
            q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
            return dict(
                dias=q("SELECT COUNT(*) FROM cash_days"),
                entradas=q("SELECT COUNT(*) FROM cash_entries"),
                caja=q("SELECT COALESCE(SUM(total),0) FROM cash_entries"),
                efectivo=q("SELECT COALESCE(SUM(cash),0) FROM cash_entries"),
                gastos=q("SELECT COALESCE(SUM(expenses),0) FROM cash_entries"),
                revisiones=q("SELECT COALESCE(SUM(revision),0) FROM cash_entries"),
                movimientos=q("SELECT COUNT(*) FROM stock_movements"),
                stock=q("SELECT COALESCE(SUM(quantity),0) FROM stock_actual"),
                articulos=q("SELECT COUNT(*) FROM articles"),
                sale_items=q("SELECT COUNT(*) FROM sale_items"),
                factufacil=q("SELECT COUNT(*) FROM factufacil_loads"),
                seguimiento=q("SELECT COUNT(*) FROM tracked_works"),
                laboratorios=q("SELECT COUNT(*) FROM laboratories"),
                pedidos=q("SELECT COUNT(*) FROM orders"),
                arqueos=q("SELECT COUNT(*) FROM cash_counts"))

    antes = foto()
    primera = admin.authenticate_operator("leti", CLAVE_LETI)
    admin.audit_saleswoman_override(primera.token, "Sol", envelope="1001")
    segunda = admin.switch_operator(primera.token, "sol", CLAVE_SOL)
    admin.logout_operator(segunda.token)
    with pytest.raises(InvalidCashDayError):
        admin.authenticate_operator("leti", "incorrecta")
    assert foto() == antes


def test_ninguna_migracion_nueva(repo):
    """El esquema de V1-019A ya alcanzaba: la sesión vive en memoria.

    Lo que esto afirma es que el login no agregó tabla ninguna, y por eso mira
    el esquema que usa y no cuál es la última migración del repositorio: cuando
    llegó V1-020 con la 031, «la última es la 030» se volvió falso sin que nada
    del login hubiera cambiado. Es exactamente el caso que documenta
    `tests/migration_chain.py`.
    """
    with repo._connection() as con:
        versiones = {f[0] for f in con.execute("SELECT version FROM schema_migrations")}
        tablas = {f[0] for f in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "030" in versiones
    # La sesión de operadora no persiste en ningún lado: vive en memoria.
    assert not [tabla for tabla in tablas if "session" in tabla.lower()]


def test_la_integridad_no_se_resiente(repo, admin, leti):
    admin.authenticate_operator("leti", CLAVE_LETI)
    with repo._connection() as con:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []


# --------------------------------------------------------------------------
# La pantalla
# --------------------------------------------------------------------------

FUENTE = open("CajaDiaria.py", encoding="utf-8").read()


def test_la_caja_pide_identificarse_al_abrir():
    assert "def pedir_login_operadora(" in FUENTE
    assert "authenticate_operator(" in FUENTE


def test_la_pantalla_muestra_quien_esta_operando():
    assert "Operando:" in FUENTE


def test_cambiar_operadora_no_vive_dentro_de_admin():
    """Tiene que estar a mano: es una acción de todos los días."""
    assert "Cambiar operadora" in FUENTE
    admin_panel = FUENTE.index("def mostrar_panel_administrador(")
    assert FUENTE.index("Cambiar operadora") < admin_panel


def test_el_responsable_sale_de_la_sesion_y_no_del_entorno():
    # La única mención que queda es la del comentario que explica de dónde
    # salía antes; no hay una sola lectura de la variable.
    assert "os.environ.get(\"BC_CAJA_RESPONSABLE\"" not in FUENTE
    assert "os.environ.get('BC_CAJA_RESPONSABLE'" not in FUENTE
    assert "sesion_caja[" in FUENTE
    assert "operadora_actual()" in FUENTE


def test_cancelar_el_login_no_deja_la_caja_usable():
    """Dejarla abierta «sin sesión» sería volver a la operación anónima, y
    encima con la ilusión de que hay control."""
    bloque = FUENTE[FUENTE.index("def exigir_login_inicial():"):][:700]
    assert "ventana.destroy()" in bloque
    salir = FUENTE[FUENTE.index("def cerrar_sesion_operadora():"):][:700]
    assert "ventana.destroy()" in salir


def test_el_arqueo_de_apertura_lo_firma_quien_esta_operando():
    """Antes salía de una variable de entorno y quedaba firmado «Caja PC», que
    no es nadie."""
    bloque = FUENTE[FUENTE.index("_sesion_apertura = operadora_actual()"):][:400]
    assert "_sesion_apertura.display_name" in bloque
