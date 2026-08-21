"""Asienta un stock inicial **estimado** para un artículo que sigue sin conteo.

Existe porque una estimación no es un conteo y no debe disfrazarse de uno. El
movimiento entra por el camino de siempre —`INGRESO_ADMINISTRATIVO` con motivo
`INVENTARIO_INICIAL`, que es lo que realmente es: la primera vez que el artículo
tiene unidades— pero el pendiente **no** se cierra como `PHYSICAL_COUNT_CONFIRMED`.
Se cierra como `ESTIMATED_INITIAL_STOCK`, y la diferencia importa: el día que
alguien cuente de verdad, la corrección será un movimiento compensatorio y se va
a poder explicar por qué hacía falta.

Las cifras que declararon las fuentes quedan guardadas al lado de la estimación.
No se borran ni se reescriben.

    python tools/stock_inicial_estimado_optica.py --sku 000010 --sucursal ASUNCION \
        --cantidad 100 [--base <ruta>] [--confirmar]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from modulos.caja_diaria.config import resolve_data_paths  # noqa: E402
from modulos.comercial.application.comercial_controller import (  # noqa: E402
    build_comercial_controller,
)

PENDIENTE = "STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION"
ESTIMADO = "ESTIMATED_INITIAL_STOCK"
ACTOR = "COMMAND_CENTER/BC-OPTICA-CONCILIACION-INVENTARIO-CORREGIDO-V1-010"

lineas: list[str] = []
fallas: list[str] = []


def registrar(texto: str = "") -> None:
    print(texto, flush=True)
    lineas.append(texto)


def comprobar(condicion: bool, descripcion: str) -> bool:
    registrar(f"  {'OK  ' if condicion else 'FALLA'} {descripcion}")
    if not condicion:
        fallas.append(descripcion)
    return bool(condicion)


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def radiografia(base: Path) -> dict:
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        q = lambda s, *a: c.execute(s, a).fetchone()[0]  # noqa: E731
        return dict(
            articulos=q("SELECT COUNT(*) FROM articles"),
            activos=q("SELECT COUNT(*) FROM articles WHERE active=1"),
            movimientos=q("SELECT COUNT(*) FROM stock_movements"),
            asuncion=q("SELECT COALESCE(SUM(quantity),0) FROM stock_movements WHERE destination='ASUNCION'"),
            pilar=q("SELECT COALESCE(SUM(quantity),0) FROM stock_movements WHERE destination='PILAR'"),
            entradas=q("SELECT COUNT(*) FROM cash_entries"),
            suma_caja=q("SELECT COALESCE(SUM(total),0) FROM cash_entries"),
            sale_items=q("SELECT COUNT(*) FROM sale_items"),
            cash_days=q("SELECT COUNT(*) FROM cash_days"),
            orders=q("SELECT COUNT(*) FROM orders"),
            integridad=q("PRAGMA integrity_check"),
            fk=len(c.execute("PRAGMA foreign_key_check").fetchall()),
            negativos=q("SELECT COUNT(*) FROM stock_actual WHERE quantity<0"),
            huerfanos=q("SELECT COUNT(*) FROM stock_movements sm LEFT JOIN articles a"
                        " ON a.id=sm.article_id WHERE a.id IS NULL"),
            efectos=q("SELECT COUNT(*) FROM event_effects ee LEFT JOIN domain_events de"
                      " ON de.event_id=ee.event_id WHERE de.event_id IS NULL"),
        )
    finally:
        c.close()


def stock(base: Path, sku: str, sucursal: str) -> int:
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        return c.execute(
            "SELECT COALESCE(SUM(sm.quantity),0) FROM stock_movements sm"
            " JOIN articles a ON a.id=sm.article_id WHERE a.sku=? AND sm.destination=?",
            (sku, sucursal)).fetchone()[0]
    finally:
        c.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sku", required=True)
    parser.add_argument("--sucursal", required=True, choices=("ASUNCION", "PILAR"))
    parser.add_argument("--cantidad", required=True, type=int)
    parser.add_argument("--base", default=None)
    parser.add_argument("--confirmar", action="store_true")
    args = parser.parse_args()

    base = Path(args.base) if args.base else Path(resolve_data_paths().database)
    antes = radiografia(base)
    otras = "PILAR" if args.sucursal == "ASUNCION" else "ASUNCION"

    registrar("STOCK INICIAL ESTIMADO")
    registrar(f"base     : {base}")
    registrar(f"sha256   : {sha256(base)}")
    registrar(f"articulo : {args.sku} en {args.sucursal}, cantidad estimada {args.cantidad}")
    registrar()

    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    articulo = c.execute("SELECT id, sku, name, nature, notes FROM articles WHERE sku=?",
                         (args.sku,)).fetchone()
    pendiente = c.execute(
        "SELECT al.details_json FROM admin_audit_log al WHERE al.action=? AND al.target_id=?"
        " AND json_extract(al.details_json,'$.sucursal')=?",
        (PENDIENTE, articulo["id"] if articulo else "", args.sucursal)).fetchone()
    ya_cerrado = c.execute(
        "SELECT COUNT(*) FROM admin_audit_log WHERE action IN (?, 'PHYSICAL_COUNT_CONFIRMED')"
        " AND target_id=? AND json_extract(details_json,'$.sucursal')=?",
        (ESTIMADO, articulo["id"] if articulo else "", args.sucursal)).fetchone()[0]
    c.close()

    registrar("== guardas ==")
    comprobar(articulo is not None, f"{args.sku} existe en el catalogo")
    if articulo is None:
        return 1
    comprobar(articulo["nature"] == "PRODUCTO_STOCKEABLE",
              f"{args.sku} es PRODUCTO_STOCKEABLE ({articulo['nature']})")
    comprobar(pendiente is not None,
              f"{args.sku} en {args.sucursal} tiene un pendiente abierto")
    comprobar(not ya_cerrado, f"{args.sku} en {args.sucursal} no fue cerrado antes")
    actual = stock(base, args.sku, args.sucursal)
    comprobar(actual == 0, f"{args.sku} en {args.sucursal} no tiene unidades todavia ({actual})")
    intacta = stock(base, args.sku, otras)
    comprobar(args.cantidad > 0, f"la cantidad estimada es positiva ({args.cantidad})")
    if fallas:
        registrar()
        registrar("No se escribe nada.")
        return 1
    detalle_previo = json.loads(pendiente["details_json"])
    registrar(f"  ---  la fuente declaraba {detalle_previo.get('source_reported_quantity')} "
              f"({detalle_previo.get('fuente')}, corte {detalle_previo.get('corte')})")
    registrar(f"  ---  {args.sku} en {otras} tiene {intacta} unidades y NO se toca")
    registrar()

    if not args.confirmar:
        registrar("NO SE ESCRIBIO NADA: falta --confirmar.")
        registrar(f"Esto haria: un movimiento de {args.cantidad} unidades en {args.sucursal}, "
                  f"y cerraria el pendiente como {ESTIMADO} -- no como conteo fisico.")
        return 0

    registrar("== backup verificable ==")
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    respaldo = base.parent / "Backups" / f"bc-caja-preestimado-{marca}.sqlite3"
    respaldo.parent.mkdir(parents=True, exist_ok=True)
    fuente = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        destino = sqlite3.connect(str(respaldo))
        try:
            fuente.backup(destino)
        finally:
            destino.close()
    finally:
        fuente.close()
    registrar(f"  archivo: {respaldo}")
    registrar(f"  sha256 : {sha256(respaldo)}")
    comprobar(radiografia(respaldo) == antes, "el backup tiene el mismo contenido que la base")
    if fallas:
        registrar("El backup no quedo bien. No se escribe nada.")
        return 1
    registrar()

    cuando = datetime.now(timezone.utc).replace(microsecond=0)
    fecha = cuando.date().isoformat()
    corrida = f"estimado-{args.sku}-{args.sucursal.lower()}-{fecha.replace('-', '')}"
    ctrl = build_comercial_controller(base)
    try:
        registrar("== movimiento ==")
        hecho = ctrl.cargar_stock_inicial(
            [(articulo["id"], args.sucursal, args.cantidad)], actor=ACTOR,
            origen=(f"Stock inicial ESTIMADO del {fecha} en {args.sucursal} para {args.sku} "
                    f"{articulo['name']}. Cantidad autorizada por el dueno: {args.cantidad}. "
                    f"NO es un conteo fisico exacto: es una estimacion operativa. Las cifras "
                    f"que declararon las fuentes -2.860 el 2026-08-03 y 2.857 el 2026-08-19- "
                    f"no se aceptaron y quedan como evidencia historica. Si mas adelante hay "
                    f"un recuento real, la diferencia se corrige con un movimiento "
                    f"compensatorio"),
            run_id=corrida, momento=cuando)
        registrar(f"  {hecho.rows_imported} movimiento, corrida {corrida}")
        # La nota del articulo tambien lo dice, para que se vea sin consultar la bitacora.
        ctrl.guardar_articulo(
            article_id=articulo["id"], sku=articulo["sku"], name=articulo["name"],
            nature=articulo["nature"], actor=ACTOR,
            notes=(f"{articulo['notes']} || {ESTIMADO} en {args.sucursal}: {args.cantidad} "
                   f"unidades el {fecha}, estimacion operativa autorizada por el dueno, NO un "
                   f"conteo fisico. Fuentes anteriores: 2.860 y 2.857, ninguna aceptada"))
    finally:
        ctrl.close()

    conexion = sqlite3.connect(str(base))
    try:
        conexion.execute(
            "INSERT INTO admin_audit_log(id, actor, action, target_type, target_id,"
            " result, details_json, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (str(uuid4()), ACTOR, ESTIMADO, "article", articulo["id"], "ESTIMADO",
             json.dumps(dict(
                 sku=args.sku, nombre=articulo["name"], sucursal=args.sucursal,
                 estimated_quantity=args.cantidad,
                 es_conteo_fisico=False,
                 cierra=PENDIENTE,
                 source_reported_quantities=[
                     dict(valor=detalle_previo.get("source_reported_quantity"),
                          fuente=detalle_previo.get("fuente"),
                          corte=detalle_previo.get("corte")),
                     dict(valor=2857, fuente="Inventario PC.xls#8397", corte="2026-08-19")],
                 ninguna_fuente_aceptada=True,
                 run_id=corrida, decidido_el=fecha,
                 si_hay_recuento_real="la diferencia se corrige con un movimiento compensatorio"),
                 ensure_ascii=False, sort_keys=True),
             cuando.isoformat()))
        conexion.commit()
    finally:
        conexion.close()
    registrar(f"  pendiente cerrado como {ESTIMADO}, no como conteo fisico")
    registrar()

    registrar("== verificacion ==")
    despues = radiografia(base)
    comprobar(stock(base, args.sku, args.sucursal) == args.cantidad,
              f"{args.sku} en {args.sucursal} = {args.cantidad}")
    comprobar(stock(base, args.sku, otras) == intacta,
              f"{args.sku} en {otras} sigue en {intacta}, intacto")
    clave = args.sucursal.lower()
    comprobar(despues[clave] == antes[clave] + args.cantidad,
              f"stock {args.sucursal}: {antes[clave]} -> {despues[clave]}")
    otra_clave = otras.lower()
    comprobar(despues[otra_clave] == antes[otra_clave],
              f"stock {otras}: {antes[otra_clave]} sin cambios")
    comprobar(despues["movimientos"] == antes["movimientos"] + 1,
              f"movimientos: {antes['movimientos']} -> {despues['movimientos']}")
    comprobar(despues["articulos"] == antes["articulos"]
              and despues["activos"] == antes["activos"],
              f"catalogo sin cambios: {antes['articulos']} articulos, {antes['activos']} activos")
    comprobar(despues["integridad"] == "ok", f"integrity_check: {despues['integridad']}")
    comprobar(despues["fk"] == 0, f"foreign_key_check: {despues['fk']}")
    comprobar(despues["negativos"] == 0, f"stock negativo: {despues['negativos']}")
    comprobar(despues["huerfanos"] == 0, f"huerfanos: {despues['huerfanos']}")
    comprobar(despues["efectos"] == 0, f"efectos sin hecho: {despues['efectos']}")
    for k in ("entradas", "suma_caja", "sale_items", "cash_days", "orders"):
        comprobar(despues[k] == antes[k], f"Caja, {k}: {antes[k]}")
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    ids = ("inventario-inicial-asuncion-20260803", "inventario-inicial-pilar-20260810")
    comprobar(c.execute("SELECT COUNT(*) FROM stock_movements WHERE document_id IN (?,?)",
                        ids).fetchone()[0] == 3583,
              "V1-008 intacta: 3.583 movimientos")
    comprobar(c.execute("SELECT COUNT(*) FROM admin_audit_log WHERE action='PHYSICAL_COUNT_CONFIRMED'"
                        " AND target_id=?", (articulo["id"],)).fetchone()[0] == 0,
              "no se registro PHYSICAL_COUNT_CONFIRMED: no hubo conteo fisico")
    c.close()
    registrar()
    registrar(f"sha256 despues: {sha256(base)}")
    registrar(f"VEREDICTO: {'PASS' if not fallas else 'FALLA'} ({len(fallas)} fallas)")
    for falla in fallas:
        registrar(f"  - {falla}")
    if fallas:
        registrar()
        registrar("Para volver atras: cerrar BC Caja, borrar la base con su -wal y -shm, "
                  f"y copiar {respaldo} encima")
    return 0 if not fallas else 1


if __name__ == "__main__":
    raise SystemExit(main())
