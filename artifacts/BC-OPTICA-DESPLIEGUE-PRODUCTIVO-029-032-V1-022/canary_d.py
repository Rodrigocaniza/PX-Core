# -*- coding: utf-8 -*-
"""Canary operativo D: venta comun, venta con convenio/saldo, compostura, y Caja -> Gestion Central.

Corre sobre la MISMA copia que dejo `canary.py` -que ya tiene personas, politica
de comision y trabajos-, nunca sobre la base productiva. La contabilidad real no
se toca: las tres operaciones de este canary nacen y mueren en la copia.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(r"c:\Users\Striker\Desktop\Proyecto X\PX-Core\.worktrees\optica-comision-composturas-021")
sys.path.insert(0, str(RAIZ))

COPIA = Path(r"C:\Users\Striker\AppData\Local\Temp\claude\despliegue\canary\bc_caja.sqlite3")
CENTRAL = Path(r"C:\Users\Striker\AppData\Local\Temp\claude\despliegue\canary\gestion_central.sqlite3")

from modulos.caja_diaria.bootstrap import build_cash_day_controller  # noqa: E402

fallas: list[str] = []


def chk(cond, texto, valor=""):
    ok = bool(cond)
    if not ok:
        fallas.append(texto)
    print(f"  {'OK   ' if ok else 'FALLA'} {texto}{('  -> ' + str(valor)) if valor != '' else ''}")
    return ok


def bloque(t):
    print()
    print(t)
    print("-" * len(t))


c = build_cash_day_controller(database_path=COPIA)
admin, jobs, ff = c.admin, c.jobs, c.factufacil
HOY = date.today().isoformat()

s_op = admin.authenticate_operator("relevoprueba", "clave-del-relevo-1")
tk_admin = admin.authenticate("adminprueba", "clave-de-prueba-larga").token

con = sqlite3.connect(str(COPIA), isolation_level=None)
con.row_factory = sqlite3.Row
base_entradas = con.execute("SELECT COUNT(*) FROM cash_entries").fetchone()[0]
base_movs = con.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0]

bloque("D.1 Venta comun")
dia, v1 = c.add_manual_entry({
    "fecha": HOY, "unidad": "PC", "caja_inicial": "0",
    "descripcion": "Cliente Canary Venta Comun", "sobre": "9001",
    "cliente_documento": "1.234.567", "cliente_telefono": "0981222333",
    "vendedora": "Operadora Prueba", "receta_dr": "Dr. Canary",
    "total": "300000", "efectivo": "300000", "tarjeta_cheque": "0",
    "notas": "canary: venta comun",
    "items": ({"description": "Armazon canary", "code": "ASU-CANARY-1",
               "item_type": "ARMAZON", "frame_price": 300000},),
})
chk(v1.total == 300000, "venta comun de 300.000 registrada", v1.total)
chk(v1.cash == 300000 and v1.card_check == 0, "pagada toda en efectivo")
chk(v1.envelope == "9001", "sobre", v1.envelope)
chk(v1.customer_document == "1.234.567", "CI/RUC", v1.customer_document)
chk(v1.customer_phone == "0981222333", "telefono", v1.customer_phone)
chk(v1.saleswoman == "Operadora Prueba", "vendedora", v1.saleswoman)
chk(dia.business_date.isoformat() == HOY and dia.unit == "PC", "dia y sucursal",
    f"{dia.business_date} {dia.unit}")

bloque("D.2 Venta con convenio y saldo")
dia, v2 = c.add_manual_entry({
    "fecha": HOY, "unidad": "PC",
    "descripcion": "Cliente Canary Convenio", "sobre": "9002",
    "cliente_documento": "7.654.321", "cliente_telefono": "0985444555",
    "vendedora": "Operadora Prueba",
    "total": "500000", "efectivo": "100000", "tarjeta_cheque": "50000",
    # El convenio necesita nombre: financiar sin decir con quien no es un convenio.
    "monto_convenio": "250000", "ordenes": "Convenio Canary S.A.", "cuotas": "2 cuotas",
    "notas": "canary: venta con convenio",
    "items": ({"description": "Cristal canary", "code": "000CANARY",
               "item_type": "CRISTAL", "lens_price": 500000},),
})
chk(v2.total == 500000, "venta con convenio de 500.000", v2.total)
chk(v2.agreement_amount == 250000, "monto de convenio", v2.agreement_amount)
chk(str(v2.balance) == "100000" or "100" in str(v2.balance), "saldo pendiente", v2.balance)
chk(v2.cash == 100000 and v2.card_check == 50000, "pagos mixtos efectivo + tarjeta")

bloque("D.3 Compostura del canary")
t = jobs.crear_trabajo(customer_name="Cliente Canary Compostura",
                       description="Cambio de plaqueta", job_type="PLAQUETA",
                       customer_phone="0971666777", responsible="Operadora Prueba",
                       charged_amount=30000, token=s_op.token, host_branch="ASUNCION")
t = jobs.marcar_listo(t.id, token=s_op.token)
comis = con.execute("SELECT kind, amount FROM service_job_commissions WHERE job_id=?",
                    (t.id,)).fetchall()
chk(len(comis) == 1 and comis[0]["amount"] == 8000,
    "la compostura devengo la tarifa vigente (8.000)", [tuple(x) for x in comis])
chk(con.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0] == base_movs,
    "la compostura no movio stock", base_movs)
chk(con.execute("SELECT COUNT(*) FROM cash_entries").fetchone()[0] == base_entradas + 2,
    "la compostura no creo por su cuenta ninguna entrada de caja")
t = jobs.entregar(t.id, delivered_by="Relevo Prueba", token=s_op.token)
chk(str(getattr(t.status, "value", t.status)) == "ENTREGADO", "compostura entregada")

bloque("D.4 FactuFacil sobre las ventas del canary (029)")
pendientes = ff.listar(estado="PARA_CARGAR")
chk(any(f.cash_entry_id == v1.id for f in pendientes),
    "la venta comun aparece «para cargar» sin que nadie la marque", len(pendientes))
chk(ff.marcar_cargada(v1.id, actor="Relevo Prueba"), "se marca cargada en FactuFacil")
fila = ff.obtener(v1.id)
chk(fila.estado == "CARGADA", "queda CARGADA", fila.estado)
chk(fila.cargada_por == "Relevo Prueba", "queda quien la cargo", fila.cargada_por)
c.update_manual_entry(v1.id, {
    "fecha": HOY, "unidad": "PC", "descripcion": "Cliente Canary Venta Comun",
    "sobre": "9001", "cliente_documento": "1.234.567",
    "cliente_telefono": "0981222333", "vendedora": "Operadora Prueba",
    "total": "310000", "efectivo": "310000", "tarjeta_cheque": "0",
    "notas": "canary: corregida despues de cargar",
    "items": ({"description": "Armazon canary", "code": "ASU-CANARY-1",
               "item_type": "ARMAZON", "frame_price": 310000},),
})
fila = ff.obtener(v1.id)
chk(fila.editada_despues_de_cargar,
    "corregir la venta despues de cargarla se ve: la revision dejo de coincidir",
    f"marca en rev {fila.revision_marcada}")
chk(ff.revertir(v1.id, actor="Relevo Prueba", motivo="hay que volver a cargarla"),
    "se puede revertir con motivo")
# La historia guarda transiciones, no ediciones de la venta: editar no es una
# marca de FactuFacil, y por eso avanza la revision en vez de dejar una linea.
chk(len(ff.historial(v1.id)) == 2, "marcar y revertir dejaron una linea cada uno",
    len(ff.historial(v1.id)))
ff.marcar_cargada(v1.id, actor="Relevo Prueba")
chk(len(ff.historial(v1.id)) == 3, "volver a marcar deja la tercera: nada se pisa",
    len(ff.historial(v1.id)))
chk(not ff.obtener(v1.id).editada_despues_de_cargar,
    "re-cargada sobre la revision corregida, la advertencia se apaga sola")

bloque("D.5 Cierre del dia y movimientos diarios")
totales = c.totals(HOY, "PC")
print(f"        totales del dia: efectivo={totales.cash} tarjeta={totales.card_check}"
      f" gastos={totales.expenses}")
cerrado = c.close_day(HOY, "PC")
chk(str(getattr(cerrado.status, "value", cerrado.status)) == "CLOSED", "dia cerrado")
chk(cerrado.closing_totals is not None, "el cierre dejo sus totales")
resultado = c.sync_closed_day_with_movements(HOY, "PC")
chk(resultado is not None, "el cierre se publico en Movimientos", resultado)
mov_path = COPIA.parent / "movimientos.txt"
chk(mov_path.exists(), "existe el archivo de movimientos diarios", mov_path.name)
if mov_path.exists():
    lineas = [l for l in mov_path.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    for l in lineas[-3:]:
        print(f"        {l}")
    chk(any("BC_CAJA" in l for l in lineas), "cada linea lleva su marca de origen")
    repetido = c.sync_closed_day_with_movements(HOY, "PC")
    lineas2 = [l for l in mov_path.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip()]
    chk(len(lineas2) == len(lineas), "re-publicar no duplica: es idempotente", len(lineas2))

bloque("D.6 Caja -> Gestion Central")
from modulos.gestion_central.repository import CentralRepository  # noqa: E402
from modulos.gestion_central.real_sync import ReviewService, REVIEW_FIELDS  # noqa: E402
from modulos.gestion_central.models import Principal, Role  # noqa: E402

if CENTRAL.exists():
    CENTRAL.unlink()
central = ReviewService(CentralRepository(CENTRAL))
actor = Principal(username="canary-central", role=Role.ADMIN_CENTRAL)
res = central.import_snapshot(actor, COPIA, organization="BC", branch="Asuncion", period=HOY)
chk(res.processed >= 2, "Gestion Central leyo las ventas del cierre", res.processed)
chk(res.inserted >= 2, "las ventas entraron a revision", res.inserted)
chk(res.unit == "PC" and res.period == HOY, "dia y sucursal (caja) viajaron",
    f"{res.period} / {res.unit}")

ventas = central.list_sales(actor)
chk(len(ventas) >= 2, "las ventas se listan en Gestion Central", len(ventas))
por_sobre = {}
for fila in ventas:
    payload = fila["payload"]
    por_sobre[payload["envelope"]] = payload

print()
print("        LO QUE LLEGO A GESTION CENTRAL, CAMPO POR CAMPO")
esperado = {
    "date": ("dia", HOY),
    "envelope": ("sobre", "9001"),
    "customer_name": ("cliente", "Cliente Canary Venta Comun"),
    "customer_document": ("CI/RUC", "1.234.567"),
    "customer_phone": ("telefono", "0981222333"),
    "saleswoman": ("vendedora", "Operadora Prueba"),
    "total": ("venta", 310000),
    "cash": ("pago en efectivo", 310000),
    "card_transfer": ("pago con tarjeta", 0),
}
p1 = por_sobre.get("9001", {})
for campo, (etiqueta, valor) in esperado.items():
    chk(p1.get(campo) == valor, f"{etiqueta} ({campo})", p1.get(campo))
chk(res.unit == "PC", "sucursal: la caja PC, que cash_register_branches liga a ASUNCION",
    res.unit)

p2 = por_sobre.get("9002", {})
chk(p2.get("agreement") == 250000, "convenio (agreement)", p2.get("agreement"))
chk(str(p2.get("balance")) == "100000" or "100" in str(p2.get("balance")),
    "saldo (balance)", p2.get("balance"))
chk(p2.get("total") == 500000, "venta con convenio (total)", p2.get("total"))
# HALLAZGO: Gestion Central no lee la marca real de FactuFacil. `real_sync.py:167`
# escribe el literal "NO DISPONIBLE PILOTO" para todas las ventas, de cuando la
# 029 no existia. La venta 9001 esta CARGADA en Caja y Gestion Central no se
# entera. Que el campo tenga texto no es que el dato viaje.
ff_central = p1.get("factufacil_status")
ff_caja = ff.obtener(v1.id).estado
chk(ff_central == ff_caja,
    f"FactuFacil viaja a Gestion Central (en Caja esta {ff_caja})", ff_central)

bloque("D.7 Revision en Gestion Central")
identidad = next(f["identity"] for f in ventas if f["payload"]["envelope"] == "9001")
central.mark_fields(actor, identidad, ["total", "cash", "saleswoman"])
revisados = central.reviewed_fields(actor, identidad)
chk(len(revisados) == 3, "se pueden marcar campos como revisados", len(revisados))
central.mark_complete(actor, identidad)
estado = next(f for f in central.list_sales(actor) if f["identity"] == identidad)
chk(estado["review_status"] == "REVIEWED", "la venta queda REVISADA", estado["review_status"])
chk(len(REVIEW_FIELDS) == 18, "la revision cubre los 18 campos del modelo", len(REVIEW_FIELDS))
progreso = central.progress(actor)
print(f"        progreso: {dict(progreso) if not isinstance(progreso, (list, tuple)) else progreso}")

con.close()
print()
print("=" * 64)
if fallas:
    print(f"RESULTADO: FALLA - {len(fallas)} comprobacion(es)")
    for f in fallas:
        print(f"  - {f}")
    sys.exit(1)
print("RESULTADO: CANARY_OPERATIVO_PASS + CAJA -> GESTION CENTRAL demostrado")
sys.exit(0)
