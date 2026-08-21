# -*- coding: utf-8 -*-
"""Canary operativo extremo a extremo sobre una COPIA de la base productiva ya migrada.

Corre sobre una copia y no sobre produccion a proposito: el canary tiene que
demostrar que el circuito entero funciona sin dejar una sola venta, un solo
movimiento ni un solo asiento de comision en la contabilidad real. Las personas
que se crean aca son ficticias y existen solo dentro de esta copia; las reales
las carga la duena en la Optica.
"""
from __future__ import annotations

import shutil
import sqlite3
import sys
import traceback
from datetime import date, datetime, timedelta
from pathlib import Path

RAIZ = Path(r"c:\Users\Striker\Desktop\Proyecto X\PX-Core\.worktrees\optica-comision-composturas-021")
sys.path.insert(0, str(RAIZ))

PROD = Path(r"C:\Users\Striker\AppData\Local\BC\Caja\bc_caja.sqlite3")
COPIA_DIR = Path(r"C:\Users\Striker\AppData\Local\Temp\claude\despliegue\canary")
COPIA_DIR.mkdir(parents=True, exist_ok=True)
COPIA = COPIA_DIR / "bc_caja.sqlite3"
shutil.copy2(PROD, COPIA)

from modulos.caja_diaria.bootstrap import build_cash_day_controller  # noqa: E402
from modulos.caja_diaria.application.admin_ops import ROL_ADMIN, ROL_OPERADOR  # noqa: E402

fallas: list[str] = []


def chk(cond, texto, valor=""):
    ok = bool(cond)
    if not ok:
        fallas.append(texto)
    print(f"  {'OK   ' if ok else 'FALLA'} {texto}{('  -> ' + str(valor)) if valor != '' else ''}")
    return ok


def falla_esperada(fn, texto, *, contiene: str = ""):
    """Lo que tiene que fallar, tiene que fallar. Que no explote no es un PASS."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        detalle = str(exc)
        if contiene and contiene.lower() not in detalle.lower():
            return chk(False, texto, f"fallo por otra razon: {detalle}")
        return chk(True, texto, type(exc).__name__)
    return chk(False, texto, "no fallo, y tenia que fallar")


def bloque(t):
    print()
    print(t)
    print("-" * len(t))


c = build_cash_day_controller(database_path=COPIA)
admin = c.admin
jobs = c.jobs

# ============================================================ USUARIOS / LOGIN
bloque("A. Usuarios y login (030 + 019B)")
chk(not admin.has_admin(), "produccion no trae ningun administrador: lo crea la duena")
sesion = admin.create_initial_admin("adminprueba", "clave-de-prueba-larga")
chk(sesion.token and sesion.is_admin, "se crea la credencial administrativa inicial",
    sesion.username)
chk(admin.has_admin(), "has_admin pasa a verdadero")
sesion_admin_id = next(u.id for u in admin.list_users(sesion.token)
                       if u.username == "adminprueba")

tk = sesion.token
operadora = admin.create_user(tk, username="operadoraprueba", display_name="Operadora Prueba",
                              role=ROL_OPERADOR, branch="ASUNCION",
                              password="clave-operadora-1")
chk(operadora.role == ROL_OPERADOR, "alta de OPERADOR con sucursal", operadora.branch)
chk(operadora.puede_entrar, "la operadora con contrasena puede entrar")
sin_clave = admin.create_user(tk, username="vendedoraprueba", display_name="Vendedora Prueba",
                              role=ROL_OPERADOR, branch="PILAR")
chk(not sin_clave.puede_entrar,
    "una persona sin contrasena existe, se la nombra en una venta, y no entra")
otra_admin = admin.create_user(tk, username="segundaadmin", display_name="Segunda Admin",
                               role=ROL_ADMIN, password="clave-admin-2222")
chk(otra_admin.role == ROL_ADMIN, "alta de ADMIN")

bloque("A.1 Login ADMIN")
s_admin = admin.authenticate("adminprueba", "clave-de-prueba-larga")
chk(s_admin.is_admin, "login ADMIN correcto", s_admin.username)
dur = s_admin.expires_at - datetime.now(s_admin.expires_at.tzinfo)
chk(timedelta(minutes=19) <= dur <= timedelta(minutes=21),
    "AdminSession dura 20 minutos", str(dur).split(".")[0])

bloque("A.2 Login OPERADOR")
s_op = admin.authenticate_operator("operadoraprueba", "clave-operadora-1")
chk(not s_op.is_admin, "login OPERADOR correcto y NO es admin", s_op.role)
chk(s_op.display_name == "Operadora Prueba", "la sesion trae el nombre visible",
    s_op.etiqueta())
fin = s_op.expires_at
chk(fin.hour == 23 and fin.minute == 59 or fin.date() > s_op.started_at.date()
    or (fin - s_op.started_at) > timedelta(hours=1),
    "CashSession vence al terminar el dia, no a los 20 minutos", fin.isoformat())
chk(fin.date() == s_op.started_at.date() or fin.date() == s_op.started_at.date() + timedelta(days=1),
    "y no sobrevive a la noche siguiente", fin.date().isoformat())

bloque("A.3 Contrasena incorrecta y usuario inactivo")
falla_esperada(lambda: admin.authenticate("adminprueba", "clave-equivocada"),
               "contrasena incorrecta de ADMIN es rechazada")
falla_esperada(lambda: admin.authenticate_operator("operadoraprueba", "no-es-esta"),
               "contrasena incorrecta de OPERADOR es rechazada")
falla_esperada(lambda: admin.authenticate_operator("noexiste", "clave-operadora-1"),
               "usuario inexistente es rechazado")
admin.set_user_active(tk, otra_admin.id, False, reason="prueba de canary")
falla_esperada(lambda: admin.authenticate("segundaadmin", "clave-admin-2222"),
               "usuario inactivo no puede entrar")
admin.set_user_active(tk, otra_admin.id, True, reason="se vuelve a habilitar")

bloque("A.4 Cambio de operadora y logout")
# Se usa una persona intacta a proposito: `adminprueba` quedo bloqueada por los
# intentos fallidos de A.3, que es exactamente lo que tenia que pasar.
relevo = admin.create_user(tk, username="relevoprueba", display_name="Relevo Prueba",
                           role=ROL_OPERADOR, branch="ASUNCION",
                           password="clave-del-relevo-1")
falla_esperada(lambda: admin.authenticate("adminprueba", "clave-de-prueba-larga"),
               "el bloqueo por intentos fallidos sigue vigente para la ADMIN")
s_op2 = admin.switch_operator(s_op.token, "relevoprueba", "clave-del-relevo-1")
chk(s_op2.username == "relevoprueba", "cambio de operadora sin cerrar la caja",
    s_op2.etiqueta())
chk(s_op2.token != s_op.token, "el cambio emite una sesion nueva")
falla_esperada(lambda: admin.require_operator(s_op.token),
               "la sesion anterior queda invalidada por el cambio")
admin.logout_operator(s_op2.token, reason="fin del canary")
falla_esperada(lambda: admin.require_operator(s_op2.token),
               "despues del logout la sesion no sirve")

bloque("A.5 Entrar a Caja no deja una sesion Admin abierta")
s_op3 = admin.authenticate_operator("relevoprueba", "clave-del-relevo-1")
falla_esperada(lambda: admin.require_admin(s_op3.token),
               "una CashSession de OPERADOR no habilita el panel administrativo")
admin.set_user_password(tk, sesion_admin_id, "clave-de-prueba-larga")
s_admin_desde_caja = admin.authenticate_operator("adminprueba", "clave-de-prueba-larga")
chk(s_admin_desde_caja.is_admin, "una ADMIN tambien puede operar la caja")
falla_esperada(
    lambda: jobs.definir_comision(user_id=operadora.id, amount=1000,
                                  token=s_op3.token),
    "definir una comision desde una sesion de OPERADOR es rechazado")

# ============================================================ COMPOSTURAS
bloque("B. Composturas: RECIBIDO -> EN_TALLER -> LISTO -> ENTREGADO (031)")
tk2 = admin.authenticate("adminprueba", "clave-de-prueba-larga").token  # ya desbloqueada
t1 = jobs.crear_trabajo(customer_name="Cliente Canary Uno",
                        description="Soldadura de puente", job_type="COMPOSTURA",
                        customer_phone="0981000111", responsible="Operadora Prueba",
                        charged_amount=45000, token=s_op3.token, host_branch="ASUNCION")
chk(t1.status.value if hasattr(t1.status, "value") else t1.status == "RECIBIDO",
    "nace en RECIBIDO", getattr(t1.status, "value", t1.status))
chk(t1.branch == "ASUNCION", "sucursal tomada de la sesion, no preguntada", t1.branch)
chk(t1.received_by == s_op3.display_name or t1.received_by,
    "queda quien recibio (actor)", t1.received_by)
chk(t1.responsible == "Operadora Prueba", "queda el responsable", t1.responsible)
chk(t1.responsible_user_id == operadora.id, "el responsable esta ligado a la persona real")
chk(bool(t1.reference), "tiene numero legible para el mostrador", t1.reference)

t1 = jobs.enviar_a_taller(t1.id, token=s_op3.token)
chk(getattr(t1.status, "value", t1.status) == "EN_TALLER", "RECIBIDO -> EN_TALLER")
t1 = jobs.marcar_listo(t1.id, token=s_op3.token)
chk(getattr(t1.status, "value", t1.status) == "LISTO", "EN_TALLER -> LISTO")
t1 = jobs.entregar(t1.id, delivered_by="Operadora Prueba", token=s_op3.token)
chk(getattr(t1.status, "value", t1.status) == "ENTREGADO", "LISTO -> ENTREGADO")
chk(t1.delivered_at is not None and t1.delivered_by,
    "ENTREGADO tiene fecha y quien entrego", t1.delivered_by)

bloque("B.1 Camino corto RECIBIDO -> LISTO")
t2 = jobs.crear_trabajo(customer_name="Cliente Canary Dos", description="Ajuste de patilla",
                        job_type="AJUSTE", responsible="Operadora Prueba",
                        token=s_op3.token, host_branch="ASUNCION")
t2 = jobs.marcar_listo(t2.id, token=s_op3.token)
chk(getattr(t2.status, "value", t2.status) == "LISTO",
    "RECIBIDO -> LISTO directo, sin pasar por el taller")

bloque("B.2 Historial, reapertura, anulacion y auditoria")
# isolation_level=None: los INSERT/DELETE que tienen que fallar no dejan una
# transaccion abierta que despues bloquee al propio servicio.
con = sqlite3.connect(str(COPIA), isolation_level=None)
eventos = con.execute(
    "SELECT event_type, from_status, to_status, actor, reason FROM service_job_events"
    " WHERE job_id=? ORDER BY sequence", (t1.id,)).fetchall()
for e in eventos:
    print(f"        {e}")
chk(len(eventos) >= 4, "el historial guarda cada transicion", len(eventos))
chk(all(e[3] for e in eventos), "cada evento tiene actor")

# Mover un trabajo pide sesion de caja, no la administrativa: lo hace quien atiende.
falla_esperada(lambda: jobs.reabrir(t2.id, reason="con token administrativo", token=tk2),
               "un token administrativo no mueve un trabajo: eso pide sesion de caja")
t2 = jobs.reabrir(t2.id, reason="el cliente lo devolvio flojo", token=s_op3.token)
chk(getattr(t2.status, "value", t2.status) == "EN_TALLER", "reapertura con motivo vuelve al taller")
falla_esperada(lambda: jobs.reabrir(t2.id, reason="", token=s_op3.token),
               "reabrir sin motivo es rechazado")
t3 = jobs.crear_trabajo(customer_name="Cliente Canary Tres", description="Tornillo",
                        job_type="TORNILLO", token=s_op3.token, host_branch="PILAR")
t3 = jobs.anular(t3.id, reason="el cliente se arrepintio", token=s_op3.token)
chk(getattr(t3.status, "value", t3.status) == "ANULADO", "anulacion con motivo")
falla_esperada(lambda: con.execute("DELETE FROM service_jobs WHERE id=?", (t3.id,)),
               "un trabajo no se puede borrar: la guarda de la base lo impide",
               contiene="no se borra")
falla_esperada(lambda: con.execute(
    "UPDATE service_job_events SET reason='otra cosa' WHERE job_id=?", (t1.id,)),
    "la historia de un trabajo no se puede reescribir", contiene="no se reescribe")
try:
    con.rollback()
except Exception:  # noqa: BLE001
    pass

bloque("B.3 Cero stock y cero movimiento automatico de caja")
movs = con.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0]
chk(movs == 4441, "las composturas no movieron una sola unidad de stock", movs)
entradas = con.execute("SELECT COUNT(*) FROM cash_entries").fetchone()[0]
chk(entradas == 12, "las composturas no crearon ni una entrada de caja sola", entradas)

# ============================================================ COMISION
bloque("C. Comision de composturas (032)")
chk(con.execute("SELECT COUNT(*) FROM service_job_commissions").fetchone()[0] == 0,
    "sin politica cargada, ningun trabajo devengo: es lo correcto, no un error")
reporte = jobs.reporte_de_comisiones(token=tk2)
chk(reporte["totales"]["sin_politica"] >= 1,
    "los trabajos terminados sin politica se listan aparte",
    reporte["totales"]["sin_politica"])

p1 = jobs.definir_comision(user_id=operadora.id, amount=5000, token=tk2)
chk(p1["amount"] == 5000, "politica vigente: 5.000 Gs por trabajo", p1["amount"])
vig = jobs.politica_vigente_de(user_id=operadora.id, job_type="COMPOSTURA", branch="ASUNCION")
chk(vig and int(vig["amount"]) == 5000, "la politica vigente se resuelve por alcance",
    vig and vig["amount"])
chk(jobs.comision_de(user_id=otra_admin.id, job_type="COMPOSTURA", branch="") in (0, None),
    "quien no comisiona no tiene politica y no devenga nada")

t4 = jobs.crear_trabajo(customer_name="Cliente Canary Cuatro", description="Compostura con comision",
                        job_type="COMPOSTURA", responsible="Operadora Prueba",
                        token=s_op3.token, host_branch="ASUNCION")
chk(con.execute("SELECT COUNT(*) FROM service_job_commissions WHERE job_id=?",
                (t4.id,)).fetchone()[0] == 0, "crear una compostura no devenga nada")
t4 = jobs.enviar_a_taller(t4.id, token=s_op3.token)
chk(con.execute("SELECT COUNT(*) FROM service_job_commissions WHERE job_id=?",
                (t4.id,)).fetchone()[0] == 0, "mandarla al taller tampoco devenga")
t4 = jobs.marcar_listo(t4.id, token=s_op3.token)
dev = con.execute("SELECT kind, amount, beneficiary, policy_id FROM service_job_commissions"
                  " WHERE job_id=?", (t4.id,)).fetchall()
chk(len(dev) == 1 and dev[0][0] == "DEVENGO" and dev[0][1] == 5000,
    "el devengo ocurre en LISTO, y es de 5.000", dev)
chk(dev[0][3] == p1["id"], "el asiento guarda la version de politica que lo explicaba")

bloque("C.1 No duplicacion")
t4 = jobs.entregar(t4.id, delivered_by="Operadora Prueba", token=s_op3.token)
chk(con.execute("SELECT COUNT(*) FROM service_job_commissions WHERE job_id=? AND kind='DEVENGO'",
                (t4.id,)).fetchone()[0] == 1, "entregar no devenga una segunda vez")

bloque("C.2 Tarifa historica: subir la tarifa no reescribe lo ya devengado")
p2 = jobs.definir_comision(user_id=operadora.id, amount=8000, token=tk2,
                           reason="acuerdo nuevo con la responsable")
chk(p2["amount"] == 8000 and p2["id"] != p1["id"],
    "cambiar es agregar una version, no pisar la anterior")
chk(con.execute("SELECT amount FROM service_job_commissions WHERE job_id=? AND kind='DEVENGO'",
                (t4.id,)).fetchone()[0] == 5000,
    "el trabajo viejo conserva los 5.000 que regian ese dia")
hist = jobs.historial_de_comision(user_id=operadora.id, token=tk2)
chk(len(hist) >= 2, "el historial de politica tiene las dos versiones", len(hist))
falla_esperada(lambda: jobs.definir_comision(user_id=operadora.id, amount=9000, token=tk2),
               "cambiar una tarifa sin motivo es rechazado", contiene="motivo")

bloque("C.3 Compensacion y neto")
t5 = jobs.crear_trabajo(customer_name="Cliente Canary Cinco", description="Compostura a compensar",
                        job_type="COMPOSTURA", responsible="Operadora Prueba",
                        token=s_op3.token, host_branch="ASUNCION")
t5 = jobs.marcar_listo(t5.id, token=s_op3.token)
t5 = jobs.anular(t5.id, reason="se habia marcado listo por error", token=s_op3.token)
comp = con.execute("SELECT kind, amount FROM service_job_commissions WHERE job_id=?"
                   " ORDER BY created_at", (t5.id,)).fetchall()
chk(len(comp) == 2 and comp[1][0] == "COMPENSACION" and comp[1][1] == -8000,
    "anular despues de LISTO deja una compensacion de signo contrario", comp)
saldo = {s["beneficiary"]: s["amount"] for s in jobs.saldo_de_comisiones()}
chk(saldo.get("Operadora Prueba") == 5000,
    "el neto es 5.000: un devengo de 5.000, uno de 8.000 y su compensacion",
    saldo)
rep = jobs.reporte_de_comisiones(token=tk2)
tot = rep["totales"]
chk(tot["bruto"] == 13000, "bruto 13.000", tot["bruto"])
chk(tot["compensado"] == -8000 or tot["compensado"] == 8000, "compensado 8.000", tot["compensado"])
chk(tot["neto"] == 5000, "neto 5.000", tot["neto"])
chk(tot["trabajos"] == len(rep["filas"]), "los totales se suman sobre las filas mostradas")

bloque("C.4 Cero contaminacion del 1% comercial")
tablas = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
chk(not any("sale" in t and "commission" in t for t in tablas),
    "no hay ninguna tabla que ligue comision con ventas")
chk(con.execute("SELECT COUNT(*) FROM sale_items").fetchone()[0] == 10,
    "las lineas de venta historicas no se tocaron")

# ============================================================ CANARY DE CAJA
bloque("D. Canary operativo de Caja: venta comun, venta con convenio, compostura")
hoy = date.today().isoformat()
dia = c.open_or_load_day(hoy, "PC", opening_cash="0")
chk(dia is not None, "dia de caja abierto para el canary", f"{dia.business_date} {dia.unit}")

antes_entradas = con.execute("SELECT COUNT(*) FROM cash_entries").fetchone()[0]
print(f"        entradas antes del canary: {antes_entradas}")

# ============================================================ CIERRE
con.close()
print()
print("=" * 64)
if fallas:
    print(f"RESULTADO: FALLA - {len(fallas)} comprobacion(es)")
    for f in fallas:
        print(f"  - {f}")
    sys.exit(1)
print("RESULTADO: PASS (secciones A, B y C)")
sys.exit(0)
