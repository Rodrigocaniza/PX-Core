# -*- coding: utf-8 -*-
"""V1-019: quién puede usar BC Caja, con qué rol, y quién lo decidió.

La lista de personas ya existía a medias: `admin_users` tenía credenciales
reales y una columna `role` que nadie leía. Lo que se agrega es que esa lista se
pueda administrar, que el rol signifique algo, y que la vendedora de una venta
deje de salir de cuatro nombres cableados en la pantalla.

Lo que más se prueba acá no es el alta: es que el permiso lo haga cumplir el
servicio y no el hecho de que un botón esté escondido.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from modulos.caja_diaria.application.admin_ops import (
    ROL_ADMIN,
    ROL_OPERADOR,
    AdminOperations,
)
from modulos.caja_diaria.domain.errors import InvalidCashDayError
from modulos.caja_diaria.domain.models import CashDay, CashEntry
from modulos.caja_diaria.infrastructure.sqlite_repository import SQLiteCashDayRepository

CLAVE_ADMIN = "administradora-2026"
CLAVE_OTRA = "otra-clave-larga-2026"


@pytest.fixture()
def ruta(tmp_path):
    return tmp_path / "bc_caja.sqlite3"


@pytest.fixture()
def repo(ruta):
    repositorio = SQLiteCashDayRepository(ruta)
    yield repositorio
    repositorio.close()


@pytest.fixture()
def admin(repo, tmp_path):
    return AdminOperations(repo, tmp_path / "datos")


@pytest.fixture()
def sesion(admin):
    """La administradora inicial, que es como arranca cualquier instalación."""
    return admin.create_initial_admin("sol", CLAVE_ADMIN)


# --------------------------------------------------------------------------
# 15. La migración
# --------------------------------------------------------------------------

def test_la_migracion_030_esta_aplicada(repo):
    with repo._connection() as con:
        versiones = {f[0] for f in con.execute("SELECT version FROM schema_migrations")}
        columnas = {f[1] for f in con.execute("PRAGMA table_info(admin_users)")}
    assert "030" in versiones
    assert {"display_name", "branch", "created_by", "updated_by"} <= columnas


def test_la_migracion_es_idempotente(ruta, repo):
    with repo._connection() as con:
        antes = con.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    repo.migrate()
    otro = SQLiteCashDayRepository(ruta)
    try:
        with otro._connection() as con:
            despues = con.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    finally:
        otro.close()
    assert antes == despues


def test_el_administrador_que_ya_existia_conserva_su_rol_y_gana_nombre(admin, sesion):
    """Compatibilidad hacia adelante: nadie tiene que actualizar nada a mano."""
    usuarios = admin.list_users(sesion.token)
    assert [u.username for u in usuarios] == ["sol"]
    assert usuarios[0].role == ROL_ADMIN
    assert usuarios[0].display_name == "sol"
    assert usuarios[0].puede_entrar is True


# --------------------------------------------------------------------------
# 1-4. Alta y edición
# --------------------------------------------------------------------------

def test_crear_usuario(admin, sesion):
    creada = admin.create_user(
        sesion.token, username="rosa", display_name="Rosa Benítez",
        role=ROL_OPERADOR, branch="ASUNCION")
    assert creada.username == "rosa"
    assert creada.display_name == "Rosa Benítez"
    assert creada.role == ROL_OPERADOR
    assert creada.active is True
    assert creada.branch == "ASUNCION"
    assert creada.created_by == "sol"
    assert creada.puede_entrar is False, "sin contraseña no entra, y está bien"


def test_un_usuario_duplicado_queda_bloqueado(admin, sesion):
    admin.create_user(sesion.token, username="rosa", display_name="Rosa")
    with pytest.raises(InvalidCashDayError, match="Ya existe"):
        admin.create_user(sesion.token, username="ROSA", display_name="Otra Rosa")


def test_editar_el_nombre_no_cambia_el_usuario(admin, sesion):
    creada = admin.create_user(sesion.token, username="rosa", display_name="Rosa")
    editada = admin.update_user(sesion.token, creada.id, display_name="Rosa Benítez")
    assert editada.display_name == "Rosa Benítez"
    assert editada.username == "rosa"
    assert editada.role == creada.role, "cambiar el nombre no toca el rol"
    assert editada.updated_by == "sol"


def test_cambiar_el_rol(admin, sesion):
    creada = admin.create_user(sesion.token, username="rosa", display_name="Rosa")
    ascendida = admin.update_user(sesion.token, creada.id, role=ROL_ADMIN)
    assert ascendida.role == ROL_ADMIN
    assert ascendida.display_name == "Rosa", "cambiar el rol no toca el nombre"


def test_un_rol_inventado_no_se_acepta(admin, sesion):
    with pytest.raises(InvalidCashDayError, match="Rol desconocido"):
        admin.create_user(sesion.token, username="rosa", display_name="Rosa",
                          role="SUPERVISORA")


# --------------------------------------------------------------------------
# 5-7, 12. Desactivar sin borrar
# --------------------------------------------------------------------------

def test_desactivar_y_reactivar(admin, sesion):
    creada = admin.create_user(sesion.token, username="rosa", display_name="Rosa")
    baja = admin.set_user_active(sesion.token, creada.id, False, reason="dejó la óptica")
    assert baja.active is False
    alta = admin.set_user_active(sesion.token, creada.id, True)
    assert alta.active is True


def test_desactivar_no_borra_la_fila(admin, sesion, repo):
    creada = admin.create_user(sesion.token, username="rosa", display_name="Rosa")
    admin.set_user_active(sesion.token, creada.id, False)
    with repo._connection() as con:
        assert con.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0] == 2
    assert admin.get_user(sesion.token, creada.id).display_name == "Rosa"


def test_no_existe_ninguna_forma_de_borrar_un_usuario(admin):
    assert not [m for m in dir(admin) if "delete" in m or "borrar" in m]


def test_un_usuario_desactivado_no_puede_entrar(admin, sesion):
    creada = admin.create_user(sesion.token, username="rosa", display_name="Rosa",
                               password=CLAVE_OTRA)
    admin.authenticate("rosa", CLAVE_OTRA)  # activa, entra
    admin.set_user_active(sesion.token, creada.id, False)
    with pytest.raises(InvalidCashDayError):
        admin.authenticate("rosa", CLAVE_OTRA)


def test_un_usuario_desactivado_sale_de_la_lista_de_vendedoras(admin, sesion):
    creada = admin.create_user(sesion.token, username="rosa", display_name="Rosa")
    assert "Rosa" in admin.active_salespeople()
    admin.set_user_active(sesion.token, creada.id, False)
    assert "Rosa" not in admin.active_salespeople()


def test_no_se_puede_dejar_la_optica_sin_administradora(admin, sesion):
    """El único candado que importa: desactivar la última administradora que
    puede entrar deja a todos afuera del panel, sin forma de volver."""
    sol = admin.list_users(sesion.token)[0]
    with pytest.raises(InvalidCashDayError, match="administradora"):
        admin.set_user_active(sesion.token, sol.id, False)
    assert admin.get_user(sesion.token, sol.id).active is True

    # Con otra administradora que pueda entrar, sí se puede.
    admin.create_user(sesion.token, username="ana", display_name="Ana",
                      role=ROL_ADMIN, password=CLAVE_OTRA)
    admin.set_user_active(sesion.token, sol.id, False)
    sesion_ana = admin.authenticate("ana", CLAVE_OTRA)
    assert admin.get_user(sesion_ana.token, sol.id).active is False


def test_una_administradora_sin_credencial_no_cuenta_como_reemplazo(admin, sesion):
    """Tener el rol no alcanza: hay que poder entrar. Si contara, se podría
    dejar la Óptica afuera nombrando a alguien que nunca puso contraseña."""
    sol = admin.list_users(sesion.token)[0]
    admin.create_user(sesion.token, username="ana", display_name="Ana",
                      role=ROL_ADMIN)  # sin contraseña
    with pytest.raises(InvalidCashDayError, match="administradora"):
        admin.set_user_active(sesion.token, sol.id, False)


# --------------------------------------------------------------------------
# 8. La historia conserva el nombre
# --------------------------------------------------------------------------

def test_una_venta_vieja_conserva_la_vendedora_aunque_se_la_desactive(
        admin, sesion, repo):
    creada = admin.create_user(sesion.token, username="rosa", display_name="Rosa")
    repo.save(CashDay(
        business_date=date(2026, 8, 19), unit="PC", opening_cash=0, opened_by="rosa",
        entries=(CashEntry(description="Maria", envelope="1001", total=450000,
                           cash=450000, saleswoman="Rosa"),)))
    admin.set_user_active(sesion.token, creada.id, False)
    admin.update_user(sesion.token, creada.id, display_name="Rosa Benítez")
    dia = repo.get_by_date_and_unit(date(2026, 8, 19), "PC")
    assert dia.entries[0].saleswoman == "Rosa", (
        "renombrar a la persona reescribió una venta de agosto")


def test_la_vendedora_no_es_una_foreign_key_a_proposito(repo):
    """Si lo fuera, corregir un nombre cambiaría la historia."""
    with repo._connection() as con:
        claves = con.execute("PRAGMA foreign_key_list(cash_entries)").fetchall()
    assert not [f for f in claves if f[2] == "admin_users"]


# --------------------------------------------------------------------------
# 9-11. Permisos, en el backend
# --------------------------------------------------------------------------

@pytest.fixture()
def sesion_operadora(admin, sesion):
    """Una operadora con credencial: puede entrar, no puede administrar."""
    admin.create_user(sesion.token, username="rosa", display_name="Rosa",
                      role=ROL_OPERADOR, password=CLAVE_OTRA)
    return admin.authenticate("rosa", CLAVE_OTRA)


def test_la_operadora_entra_pero_su_sesion_no_es_de_administradora(sesion_operadora):
    assert sesion_operadora.role == ROL_OPERADOR
    assert sesion_operadora.is_admin is False


@pytest.mark.parametrize("accion", [
    lambda a, t: a.list_users(t),
    lambda a, t: a.create_user(t, username="nueva", display_name="Nueva"),
    lambda a, t: a.update_user(t, "cualquiera", display_name="X"),
    lambda a, t: a.set_user_active(t, "cualquiera", False),
    lambda a, t: a.set_user_password(t, "cualquiera", CLAVE_OTRA),
    lambda a, t: a.audit_rows(t),
    lambda a, t: a.update_setting(t, "branch", {"branch": "X", "cashbox": "Y"}),
])
def test_la_operadora_no_puede_invocar_acciones_administrativas(
        admin, sesion_operadora, accion):
    """Llamando al servicio directamente, sin pasar por ninguna pantalla: es la
    única forma de comprobar que el permiso no depende de esconder un botón."""
    with pytest.raises(InvalidCashDayError):
        accion(admin, sesion_operadora.token)


@pytest.mark.parametrize("accion", [
    lambda a, t: a.list_users(t),
    lambda a, t: a.audit_rows(t),
])
def test_la_administradora_si_puede(admin, sesion, accion):
    assert accion(admin, sesion.token) is not None


def test_el_intento_denegado_queda_registrado(admin, sesion, sesion_operadora):
    with pytest.raises(InvalidCashDayError):
        admin.list_users(sesion_operadora.token)
    acciones = [f["action"] for f in admin.audit_rows(sesion.token)]
    assert "ADMIN_DENIED" in acciones


def test_una_sesion_inventada_no_sirve(admin):
    with pytest.raises(InvalidCashDayError):
        admin.list_users("token-que-alguien-escribio-a-mano")


# --------------------------------------------------------------------------
# 13. Auditoría
# --------------------------------------------------------------------------

def _acciones(admin, token, tipo="admin_user"):
    return [f for f in admin.audit_rows(token, limit=200)
            if f["target_type"] == tipo]


def test_la_auditoria_registra_el_ciclo_completo(admin, sesion):
    creada = admin.create_user(sesion.token, username="rosa", display_name="Rosa")
    admin.update_user(sesion.token, creada.id, role=ROL_ADMIN)
    admin.set_user_active(sesion.token, creada.id, False, reason="licencia")
    admin.set_user_active(sesion.token, creada.id, True)
    acciones = [f["action"] for f in _acciones(admin, sesion.token)]
    for esperada in ("USER_CREATED", "USER_UPDATED", "USER_DEACTIVATED",
                     "USER_ACTIVATED"):
        assert esperada in acciones


def test_la_auditoria_guarda_el_rol_anterior_y_el_nuevo(admin, sesion):
    creada = admin.create_user(sesion.token, username="rosa", display_name="Rosa")
    admin.update_user(sesion.token, creada.id, role=ROL_ADMIN)
    fila = [f for f in _acciones(admin, sesion.token)
            if f["action"] == "USER_UPDATED"][0]
    assert ROL_OPERADOR in fila["details_json"]
    assert ROL_ADMIN in fila["details_json"]
    assert fila["actor"] == "sol"
    assert fila["recorded_at"]


def test_la_auditoria_no_se_reescribe(admin, sesion):
    creada = admin.create_user(sesion.token, username="rosa", display_name="Rosa")
    antes = len(_acciones(admin, sesion.token))
    admin.update_user(sesion.token, creada.id, display_name="Rosa B.")
    despues = _acciones(admin, sesion.token)
    assert len(despues) == antes + 1


def test_la_contrasena_nunca_se_guarda_en_texto_plano(admin, sesion, repo):
    admin.create_user(sesion.token, username="rosa", display_name="Rosa",
                      password=CLAVE_OTRA)
    with repo._connection() as con:
        volcado = " ".join(str(v) for fila in con.execute("SELECT * FROM admin_users")
                           for v in fila)
        bitacora = " ".join(f["details_json"] for f in con.execute(
            "SELECT details_json FROM admin_audit_log"))
    assert CLAVE_OTRA not in volcado
    assert CLAVE_OTRA not in bitacora


# --------------------------------------------------------------------------
# 14. Persistencia
# --------------------------------------------------------------------------

def test_reiniciar_conserva_usuarios_roles_y_estado(ruta, repo, admin, sesion,
                                                    tmp_path):
    creada = admin.create_user(sesion.token, username="rosa", display_name="Rosa",
                               role=ROL_ADMIN, branch="PILAR")
    admin.set_user_active(sesion.token, creada.id, False)
    repo.close()
    otro = SQLiteCashDayRepository(ruta)
    try:
        otro_admin = AdminOperations(otro, tmp_path / "datos")
        nueva = otro_admin.authenticate("sol", CLAVE_ADMIN)
        recargada = otro_admin.get_user(nueva.token, creada.id)
        assert recargada.display_name == "Rosa"
        assert recargada.role == ROL_ADMIN
        assert recargada.active is False
        assert recargada.branch == "PILAR"
    finally:
        otro.close()


# --------------------------------------------------------------------------
# 16-19. Lo que no se toca
# --------------------------------------------------------------------------

def test_administrar_usuarios_no_toca_nada_de_la_operacion(admin, sesion, repo):
    repo.save(CashDay(
        business_date=date(2026, 8, 19), unit="PC", opening_cash=0, opened_by="sol",
        entries=(CashEntry(description="Maria", envelope="1001", total=450000,
                           cash=450000, saleswoman="Rosa"),)))

    def foto():
        with repo._connection() as con:
            q = lambda s: con.execute(s).fetchone()[0]  # noqa: E731
            return dict(
                entradas=q("SELECT COUNT(*) FROM cash_entries"),
                caja=q("SELECT COALESCE(SUM(total),0) FROM cash_entries"),
                movimientos=q("SELECT COUNT(*) FROM stock_movements"),
                stock=q("SELECT COALESCE(SUM(quantity),0) FROM stock_actual"),
                articulos=q("SELECT COUNT(*) FROM articles"),
                sale_items=q("SELECT COUNT(*) FROM sale_items"),
                factufacil=q("SELECT COUNT(*) FROM factufacil_loads"),
                seguimiento=q("SELECT COUNT(*) FROM tracked_works"),
                laboratorios=q("SELECT COUNT(*) FROM laboratories"),
                pedidos=q("SELECT COUNT(*) FROM orders"))

    antes = foto()
    creada = admin.create_user(sesion.token, username="rosa", display_name="Rosa")
    admin.update_user(sesion.token, creada.id, role=ROL_ADMIN)
    admin.set_user_active(sesion.token, creada.id, False)
    assert foto() == antes


def test_la_integridad_de_la_base_no_se_resiente(admin, sesion, repo):
    admin.create_user(sesion.token, username="rosa", display_name="Rosa")
    with repo._connection() as con:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []


# --------------------------------------------------------------------------
# La pantalla
# --------------------------------------------------------------------------

FUENTE = open("CajaDiaria.py", encoding="utf-8").read()


def test_la_lista_de_vendedoras_ya_no_esta_cableada():
    """Cuatro nombres inventados para una maqueta estuvieron eligiendo la
    vendedora de cada venta real."""
    assert '"Ana", "Belén", "Carla", "Diana"' not in FUENTE
    assert "active_salespeople()" in FUENTE


def test_la_pantalla_de_usuarios_existe_y_llama_al_servicio():
    assert "def refrescar_usuarios(" in FUENTE
    bloque = FUENTE[FUENTE.index("def refrescar_usuarios("):][:3000]
    assert "list_users(" in bloque
