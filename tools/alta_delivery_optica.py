"""Da de alta el concepto `Delivery / Envío` en el catálogo.

Es una sola fila y no toca nada económico: un servicio no lleva stock, así que
darlo de alta no crea ni una unidad ni mueve un guaraní. El precio que queda en
el catálogo es apenas una sugerencia — lo que se cobra vive en cada línea de
venta, que es donde tiene que estar: el envío cuesta distinto según a dónde va.

Si ya existe, no lo duplica: lo reporta y no escribe.

    python tools/alta_delivery_optica.py [--base <ruta>] [--confirmar]
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
from modulos.comercial.domain.models import ArticleNature  # noqa: E402

SKU = "SERV-DELIVERY"
NOMBRE = "Delivery / Envío"
PRECIO_SUGERIDO = 20000
CATEGORIA = "Servicios"
ALTA = "DELIVERY_SERVICE_CREATED"
ACTOR = "COMMAND_CENTER/BC-OPTICA-DELIVERY-SERVICE-V1-011"

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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=None)
    parser.add_argument("--confirmar", action="store_true")
    args = parser.parse_args()

    base = Path(args.base) if args.base else Path(resolve_data_paths().database)
    antes = radiografia(base)

    registrar("ALTA DEL CONCEPTO DELIVERY / ENVIO")
    registrar(f"base   : {base}")
    registrar(f"sha256 : {sha256(base)}")
    registrar(f"antes  : {antes['articulos']} articulos ({antes['activos']} activos), "
              f"{antes['movimientos']} movimientos, ASU {antes['asuncion']} / PIL {antes['pilar']}")
    registrar()

    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    existente = c.execute("SELECT id, sku, name, nature, sale_price, active FROM articles"
                          " WHERE sku=?", (SKU,)).fetchone()
    # Un concepto equivalente que ya exista con otro codigo: no se duplica a ciegas.
    parecidos = c.execute(
        "SELECT sku, name, nature, active FROM articles WHERE sku<>? AND ("
        " lower(name) LIKE '%deliver%' OR lower(name) LIKE '%envio%'"
        " OR lower(name) LIKE '%env_o%' OR lower(name) LIKE '%flete%')", (SKU,)).fetchall()
    c.close()

    registrar("== guardas ==")
    if existente is not None:
        registrar(f"  ---  {SKU} ya existe: {existente['name']!r}, {existente['nature']}, "
                  f"precio {existente['sale_price']}, activo {existente['active']}")
        registrar("NO SE ESCRIBE NADA: el concepto ya esta. No se duplica")
        return 0
    comprobar(not parecidos,
              f"no hay otro concepto equivalente con distinto codigo ({[dict(p) for p in parecidos]})")
    if fallas:
        registrar()
        registrar("Hay un concepto parecido. Se detiene para no crear un segundo modelo "
                  "de lo mismo: revisar si corresponde reutilizarlo.")
        return 1
    registrar()

    if not args.confirmar:
        registrar("NO SE ESCRIBIO NADA: falta --confirmar.")
        registrar(f"Esto crearia un articulo {SKU} «{NOMBRE}», "
                  f"{ArticleNature.SERVICIO_NO_STOCKEABLE.value}, precio sugerido "
                  f"{PRECIO_SUGERIDO}, sin una sola unidad de stock.")
        return 0

    registrar("== backup verificable ==")
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    respaldo = base.parent / "Backups" / f"bc-caja-predelivery-{marca}.sqlite3"
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
    ctrl = build_comercial_controller(base)
    try:
        registrar("== alta ==")
        categoria = next((x for x in ctrl.listar_categorias(solo_activas=False)
                          if x.name.strip().lower() == CATEGORIA.lower()), None)
        if categoria is None:
            categoria = ctrl.crear_categoria(CATEGORIA, actor=ACTOR)
            registrar(f"  categoria «{CATEGORIA}» creada")
        articulo = ctrl.guardar_articulo(
            sku=SKU, name=NOMBRE, nature=ArticleNature.SERVICIO_NO_STOCKEABLE,
            actor=ACTOR, category_id=categoria.id, sale_price=PRECIO_SUGERIDO,
            notes=("Concepto de envio, alta V1-011. El precio del catalogo es apenas "
                   "orientativo: lo que se cobra vive en cada linea de venta, porque el "
                   "envio cuesta distinto segun a donde va. No lleva stock por naturaleza"))
        registrar(f"  {articulo.sku} «{articulo.name}» -- {articulo.nature.value}, "
                  f"precio sugerido {articulo.sale_price}")
    finally:
        ctrl.close()

    conexion = sqlite3.connect(str(base))
    try:
        conexion.execute(
            "INSERT INTO admin_audit_log(id, actor, action, target_type, target_id,"
            " result, details_json, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (str(uuid4()), ACTOR, ALTA, "article", articulo.id, "CREADO",
             json.dumps(dict(sku=SKU, nombre=NOMBRE,
                             nature="SERVICIO_NO_STOCKEABLE",
                             precio_sugerido=PRECIO_SUGERIDO,
                             precio_editable_por_venta=True,
                             lleva_stock=False,
                             categoria=CATEGORIA,
                             nota="el precio del catalogo no reescribe ventas anteriores"),
                        ensure_ascii=False, sort_keys=True),
             cuando.isoformat()))
        conexion.commit()
    finally:
        conexion.close()
    registrar()

    registrar("== verificacion ==")
    despues = radiografia(base)
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    nuevo = c.execute("SELECT sku, name, nature, sale_price, active FROM articles WHERE sku=?",
                      (SKU,)).fetchone()
    comprobar(nuevo is not None, f"{SKU} existe")
    comprobar(nuevo["nature"] == "SERVICIO_NO_STOCKEABLE", f"nature: {nuevo['nature']}")
    comprobar(nuevo["sale_price"] == PRECIO_SUGERIDO, f"precio sugerido: {nuevo['sale_price']}")
    comprobar(nuevo["active"] == 1, "queda activo y seleccionable")
    comprobar(c.execute("SELECT COUNT(*) FROM articles WHERE sku=?", (SKU,)).fetchone()[0] == 1,
              "una sola fila: no se duplico")
    comprobar(c.execute("SELECT COUNT(*) FROM stock_movements sm JOIN articles a"
                        " ON a.id=sm.article_id WHERE a.sku=?", (SKU,)).fetchone()[0] == 0,
              "no se creo una sola unidad de stock")
    c.close()
    comprobar(despues["articulos"] == antes["articulos"] + 1,
              f"articulos: {antes['articulos']} -> {despues['articulos']}")
    comprobar(despues["activos"] == antes["activos"] + 1,
              f"activos: {antes['activos']} -> {despues['activos']}")
    comprobar(despues["movimientos"] == antes["movimientos"],
              f"movimientos sin cambios: {antes['movimientos']}")
    comprobar(despues["asuncion"] == antes["asuncion"] and despues["pilar"] == antes["pilar"],
              f"stock sin cambios: ASU {antes['asuncion']} / PIL {antes['pilar']}")
    for clave, etiqueta in (("integridad", "integrity_check"), ("fk", "foreign_key_check"),
                            ("negativos", "stock negativo"), ("huerfanos", "huerfanos"),
                            ("efectos", "efectos sin hecho")):
        esperado = "ok" if clave == "integridad" else 0
        comprobar(despues[clave] == esperado, f"{etiqueta}: {despues[clave]}")
    for clave in ("entradas", "suma_caja", "sale_items"):
        comprobar(despues[clave] == antes[clave], f"Caja, {clave}: {antes[clave]}")

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
