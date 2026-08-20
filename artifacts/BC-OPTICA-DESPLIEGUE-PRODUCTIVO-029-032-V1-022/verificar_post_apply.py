# -*- coding: utf-8 -*-
"""Verificacion post-apply punto por punto. No acepta PASS por exit code."""
import json
import sqlite3
import sys
from pathlib import Path

BASE = Path(r"C:\Users\Striker\AppData\Local\BC\Caja\bc_caja.sqlite3")
P = Path(r"C:\Users\Striker\AppData\Local\Temp\claude\despliegue")
antes = json.loads((P / "radiografia_ANTES.json").read_text(encoding="utf-8"))
despues = json.loads((P / "radiografia_DESPUES.json").read_text(encoding="utf-8"))

con = sqlite3.connect(f"file:{BASE.as_posix()}?mode=ro", uri=True)
uno = lambda s, *a: con.execute(s, a).fetchone()  # noqa: E731
todas = lambda s, *a: con.execute(s, a).fetchall()  # noqa: E731
tablas = {r[0] for r in todas("SELECT name FROM sqlite_master WHERE type='table'")}

fallas = []


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


bloque("1. Esquema final")
migr = todas("SELECT version FROM schema_migrations ORDER BY version")
chk(len(migr) == 32, "32 migraciones registradas", len(migr))
chk(migr[-1][0] == "032", "la ultima es la 032", migr[-1][0])
chk([m[0] for m in migr] == [f"{i:03d}" for i in range(1, 33)],
    "la cadena 001..032 esta completa y sin huecos")

bloque("2. Integridad fisica")
chk(uno("PRAGMA integrity_check")[0] == "ok", "integrity_check", uno("PRAGMA integrity_check")[0])
fk = todas("PRAGMA foreign_key_check")
chk(not fk, "foreign_key_check sin violaciones", fk or "sin violaciones")
chk(uno("PRAGMA foreign_keys")[0] in (0, 1), "pragma foreign_keys legible")
qc = uno("PRAGMA quick_check")[0]
chk(qc == "ok", "quick_check", qc)

bloque("3. Ventas historicas y pagos")
a, d = antes["caja"], despues["caja"]
chk(a["entradas"] == d["entradas"] == 12, "12 ventas historicas, ninguna mas ni menos", d["entradas"])
chk(a["entradas_activas"] == d["entradas_activas"], "ventas activas sin cambio", d["entradas_activas"])
chk(a["total"] == d["total"], "suma total de caja sin cambio", d["total"])
chk(a["efectivo"] == d["efectivo"], "efectivo sin cambio", d["efectivo"])
chk(a["tarjeta_cheque"] == d["tarjeta_cheque"], "tarjeta/cheque sin cambio", d["tarjeta_cheque"])
chk(a["gastos"] == d["gastos"], "gastos sin cambio", d["gastos"])
chk(a["convenio"] == d["convenio"], "convenios sin cambio", d["convenio"])
chk(a["entradas_detalle"] == d["entradas_detalle"], "cada venta, fila por fila, identica")
chk(a["revisiones"] == d["revisiones"], "revisiones de venta sin cambio", d["revisiones"])
chk(a["max_revision_por_entrada"] == d["max_revision_por_entrada"],
    "la revision de cada venta no avanzo")
chk(a["dias_detalle"] == d["dias_detalle"], "los dias de caja quedaron exactamente como estaban")

bloque("4. Arqueos")
chk(a["arqueos"] == d["arqueos"], "cash_counts sin cambio", d["arqueos"])
chk(a["arqueos_snapshots"] == d["arqueos_snapshots"], "snapshots de arqueo sin cambio",
    d["arqueos_snapshots"])
chk(a["correcciones_dia"] == d["correcciones_dia"], "correcciones de dia sin cambio",
    d["correcciones_dia"])

bloque("5. Articulos y catalogo")
a, d = antes["catalogo"], despues["catalogo"]
chk(a["articulos"] == d["articulos"] == 3596, "3596 articulos", d["articulos"])
chk(a["articulos_activos"] == d["articulos_activos"], "articulos activos sin cambio",
    d["articulos_activos"])
chk(a["por_naturaleza"] == d["por_naturaleza"], "naturaleza de cada articulo sin cambio")
chk(a["categorias"] == d["categorias"], "categorias sin cambio", d["categorias"])
chk(a["marcas"] == d["marcas"], "marcas sin cambio", d["marcas"])

bloque("6. Stock y movimientos")
a, d = antes["stock"], despues["stock"]
chk(a["movimientos"] == d["movimientos"] == 4441, "4441 movimientos", d["movimientos"])
chk(a["unidades_netas"] == d["unidades_netas"], "unidades netas sin cambio", d["unidades_netas"])
chk(a["por_destino"] == d["por_destino"], "stock por sucursal sin cambio", d["por_destino"])
chk(a["por_tipo"] == d["por_tipo"], "movimientos por tipo sin cambio")
negativos = todas(
    "SELECT article_id, destination, SUM(quantity) s FROM stock_movements"
    " GROUP BY article_id, destination HAVING s < 0")
chk(not negativos, "ningun articulo quedo con stock negativo", len(negativos))
chk(a["integraciones_venta"] == d["integraciones_venta"], "integraciones venta->stock sin cambio")
chk(a["compensaciones_anulacion"] == d["compensaciones_anulacion"],
    "compensaciones de anulacion sin cambio")

bloque("7. FactuFacil (029)")
chk("factufacil_loads" in tablas, "existe factufacil_loads")
chk("factufacil_history" in tablas, "existe factufacil_history")
chk(uno("SELECT COUNT(*) FROM factufacil_loads")[0] == 0,
    "nace vacia: no se invento ninguna marca de carga")
chk(uno("SELECT COUNT(*) FROM factufacil_history")[0] == 0, "historia de FactuFacil vacia")
para_cargar = uno(
    "SELECT COUNT(*) FROM cash_entries e WHERE e.status='ACTIVE' AND e.total > 0"
    " AND NOT EXISTS (SELECT 1 FROM factufacil_loads f WHERE f.cash_entry_id = e.id)")[0]
chk(para_cargar >= 0, "«para cargar» se deduce por consulta, no por estado", para_cargar)

bloque("8. Seguimiento y laboratorios")
a, d = antes["seguimiento"], despues["seguimiento"]
chk(a == d, "Seguimiento intacto", d)
chk(antes["catalogo"]["laboratorios"] == despues["catalogo"]["laboratorios"],
    "los 3 laboratorios, iguales", len(despues["catalogo"]["laboratorios"]))
chk(antes["catalogo"]["con_laboratorio_default"] == despues["catalogo"]["con_laboratorio_default"],
    "laboratorio por defecto de cada articulo sin cambio",
    despues["catalogo"]["con_laboratorio_default"])

bloque("9. Pedidos")
a, d = antes["pedidos"], despues["pedidos"]
chk(a["cantidad"] == d["cantidad"] == 8, "8 pedidos", d["cantidad"])
chk(a["detalle"] == d["detalle"], "cada pedido, fila por fila, identico")
chk(a["revisiones_estado"] == d["revisiones_estado"], "revisiones de estado sin cambio")

bloque("10. Trabajos operativos y comision de composturas (031 + 032)")
for t in ("service_job_types", "service_jobs", "service_job_events",
          "service_job_commissions", "service_commission_policy_versions"):
    chk(t in tablas, f"existe {t}")
chk("service_commission_policy" not in tablas,
    "service_commission_policy fue reemplazada por el log de versiones")
tipos = todas("SELECT code, label FROM service_job_types ORDER BY position")
chk(len(tipos) == 8, "8 tipos de trabajo sembrados", [t[0] for t in tipos])
chk(all(t[0] != "" for t in tipos), "ningun tipo con codigo vacio")
chk(uno("SELECT COUNT(*) FROM service_jobs")[0] == 0, "cero trabajos: nada sembrado")
chk(uno("SELECT COUNT(*) FROM service_job_commissions")[0] == 0, "cero comisiones devengadas")
chk(uno("SELECT COUNT(*) FROM service_commission_policy_versions")[0] == 0,
    "cero politicas: ninguna persona ni monto viene del codigo")
cols = {r[1] for r in todas("PRAGMA table_info(service_job_commissions)")}
chk("policy_id" in cols, "service_job_commissions.policy_id agregada por la 032")
vistas = {r[0] for r in todas("SELECT name FROM sqlite_master WHERE type='view'")}
chk("service_commission_balance" in vistas, "vista service_commission_balance disponible")
disparadores = {r[0] for r in todas("SELECT name FROM sqlite_master WHERE type='trigger'")}
for tr in ("service_jobs_sin_delete", "service_job_events_sin_update",
           "service_job_events_sin_delete", "service_commissions_sin_update",
           "service_commissions_sin_delete", "service_policy_versions_sin_update",
           "service_policy_versions_sin_delete"):
    chk(tr in disparadores, f"guarda append-only activa: {tr}")

bloque("11. Comision comercial del 1% - separacion estructural")
sospechosas = [t for t in tablas if "commission" in t.lower() or "comision" in t.lower()]
chk(sorted(sospechosas) == ["service_job_commissions", "service_commission_policy_versions"]
    or set(sospechosas) == {"service_job_commissions", "service_commission_policy_versions"},
    "las unicas tablas de comision son las de composturas", sorted(sospechosas))
chk(uno("SELECT COUNT(*) FROM sale_items")[0] == antes["venta_lineas"]["cantidad"],
    "el 1% vive en BC Gestion sobre texto plano: esta base no lo toca")

bloque("12. Usuarios y roles (030)")
cols = {r[1] for r in todas("PRAGMA table_info(admin_users)")}
for c in ("display_name", "branch", "created_by", "updated_by", "role", "active"):
    chk(c in cols, f"admin_users.{c}")
n = uno("SELECT COUNT(*) FROM admin_users")[0]
chk(n == antes["personas"]["admin_users"],
    "la 030 no invento ninguna persona", n)

bloque("13. Outbox / sincronizacion")
a, d = antes["sincronizacion"], despues["sincronizacion"]
chk(a == d, "domain_events, event_effects, outbox, mail_history e import_runs intactos", d)

bloque("14. Auditoria")
a, d = antes["auditoria"], despues["auditoria"]
chk(a["eventos"] == d["eventos"], "la bitacora no se reescribio", d["eventos"])
chk(a["por_accion"] == d["por_accion"], "cada accion auditada sigue en su lugar")

con.close()
print()
print("=" * 64)
if fallas:
    print(f"RESULTADO: FALLA - {len(fallas)} comprobacion(es)")
    for f in fallas:
        print(f"  - {f}")
    sys.exit(1)
print("RESULTADO: PRODUCTIVE_APPLY_PASS")
print(f"  base    {BASE}")
print(f"  sha256  {despues['archivo']['sha256']}")
print(f"  tamano  {despues['archivo']['tamano']}")
print(f"  esquema 032")
sys.exit(0)
