# -*- coding: utf-8 -*-
"""Devuelve la categoría y la marca que V1-010 y V1-013 borraron sin querer.

Cinco artículos quedaron sin categoría ni marca porque se los guardó nombrando
sólo cuatro campos, y guardar reemplaza el artículo entero. No se perdió stock
ni dinero: se perdieron etiquetas. Pero un armazón sin marca es un armazón que
nadie encuentra.

El backup se usa como fuente de esos dos campos y de nada más. El artículo
productivo de hoy es el bueno: tiene la naturaleza corregida, las notas con la
evidencia del recuento y sus movimientos. Restaurar la fila entera sería
deshacer dos misiones para arreglar una etiqueta.

    python tools/restaurar_metadatos_articulos_optica.py [--base <ruta>]
        [--fuente <backup>] [--confirmar]
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

#: Los cinco. La lista no es una hipótesis: sale de comparar la producción con
#: el backup campo por campo sobre los 3.554 artículos que ya existían.
AFECTADOS = ("000010", "2000056", "2000070", "2000071", "2000072")

#: Última foto en la que los cinco todavía tenían sus etiquetas.
FUENTE = "bc-caja-prerecuento-20260819-142306.sqlite3"

ACCION = "ARTICLE_METADATA_RESTORED"
ACTOR = "COMMAND_CENTER/BC-OPTICA-ARTICLE-METADATA-RESTORE-V1-014"

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
            asuncion=q("SELECT COALESCE(SUM(quantity),0) FROM stock_movements"
                       " WHERE destination='ASUNCION'"),
            pilar=q("SELECT COALESCE(SUM(quantity),0) FROM stock_movements"
                    " WHERE destination='PILAR'"),
            entradas=q("SELECT COUNT(*) FROM cash_entries"),
            suma_caja=q("SELECT COALESCE(SUM(total),0) FROM cash_entries"),
            sale_items=q("SELECT COUNT(*) FROM sale_items"),
            categorias=q("SELECT COUNT(*) FROM article_categories"),
            marcas=q("SELECT COUNT(*) FROM brands"),
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


def foto_articulos(base: Path) -> dict[str, dict]:
    """Todos los artículos con sus campos, para comparar antes y después."""
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        cats = {r[0]: r[1] for r in c.execute("SELECT id, name FROM article_categories")}
        marcas = {r[0]: r[1] for r in c.execute("SELECT id, name FROM brands")}
        salida = {}
        for fila in c.execute("SELECT * FROM articles"):
            d = dict(fila)
            d.pop("updated_at", None)  # cambia por definición al escribir
            d["_categoria"] = cats.get(d["category_id"])
            d["_marca"] = marcas.get(d["brand_id"])
            salida[d["sku"]] = d
        return salida
    finally:
        c.close()


def diferencias(antes: dict[str, dict], despues: dict[str, dict]) -> list[tuple]:
    salida = []
    for sku in sorted(set(antes) | set(despues)):
        a, d = antes.get(sku), despues.get(sku)
        if a is None or d is None:
            salida.append((sku, "existencia", a is not None, d is not None))
            continue
        for campo in a:
            if campo.startswith("_"):
                continue
            if a[campo] != d[campo]:
                salida.append((sku, campo, a[campo], d[campo]))
    return salida


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=None)
    parser.add_argument("--fuente", default=None)
    parser.add_argument("--confirmar", action="store_true")
    args = parser.parse_args()

    base = Path(args.base) if args.base else Path(resolve_data_paths().database)
    fuente = (Path(args.fuente) if args.fuente
              else base.parent / "Backups" / FUENTE)

    registrar("RESTAURACION DE CATEGORIA Y MARCA")
    registrar(f"base   : {base}")
    registrar(f"sha256 : {sha256(base)}")
    registrar(f"fuente : {fuente}")
    if not fuente.exists():
        registrar("La fuente no existe. No se escribe nada.")
        return 1
    registrar(f"sha256 : {sha256(fuente)}")
    registrar()

    antes_totales = radiografia(base)
    antes_articulos = foto_articulos(base)
    historicos = foto_articulos(fuente)
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        bitacora_antes = dict(c.execute("SELECT action, COUNT(*) FROM admin_audit_log"
                                        " GROUP BY action").fetchall())
    finally:
        c.close()

    registrar("== diff exacto de los cinco ==")
    plan: list[dict] = []
    for sku in AFECTADOS:
        actual = antes_articulos.get(sku)
        viejo = historicos.get(sku)
        if actual is None:
            comprobar(False, f"{sku} no existe en produccion")
            continue
        if viejo is None:
            comprobar(False, f"{sku} no existe en la fuente historica")
            continue
        registrar(f"  {sku} «{actual['name']}»")
        registrar(f"      naturaleza : {actual['nature']}  (se conserva, no se revierte)")
        registrar(f"      categoria  : {actual['_categoria']!r} <- {viejo['_categoria']!r}")
        registrar(f"      marca      : {actual['_marca']!r} <- {viejo['_marca']!r}")
        campos = {}
        if actual["category_id"] is None and viejo["category_id"] is not None:
            campos["category_id"] = viejo["category_id"]
        if actual["brand_id"] is None and viejo["brand_id"] is not None:
            campos["brand_id"] = viejo["brand_id"]
        if not campos:
            registrar("      nada que restaurar: ya tiene sus etiquetas")
            continue
        plan.append(dict(sku=sku, id=actual["id"], campos=campos,
                         categoria=viejo["_categoria"], marca=viejo["_marca"]))
    registrar()

    registrar("== guardas ==")
    if not plan:
        registrar("NO SE ESCRIBE NADA: los cinco ya tienen categoria y marca.")
        registrar("Idempotencia: una segunda corrida no cambia nada.")
        return 0
    # Las categorias y marcas historicas tienen que seguir existiendo en
    # produccion. Si no, restaurar el id dejaria una referencia rota.
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        for paso in plan:
            for campo, tabla in (("category_id", "article_categories"), ("brand_id", "brands")):
                if campo not in paso["campos"]:
                    continue
                fila = c.execute(f"SELECT name, active FROM {tabla} WHERE id=?",
                                 (paso["campos"][campo],)).fetchone()
                comprobar(fila is not None,
                          f"{paso['sku']}: {campo} {paso['campos'][campo]} existe en produccion")
                if fila is not None:
                    comprobar(fila[1] == 1, f"{paso['sku']}: «{fila[0]}» esta activa")
    finally:
        c.close()
    if fallas:
        registrar("Alguna categoria o marca ya no esta. No se escribe nada.")
        return 1
    registrar()

    if not args.confirmar:
        registrar(f"NO SE ESCRIBIO NADA: falta --confirmar.")
        registrar(f"Esto restauraria categoria y marca en {len(plan)} articulos, "
                  "y no tocaria ningun otro campo.")
        return 0

    registrar("== backup verificable ==")
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    respaldo = base.parent / "Backups" / f"bc-caja-premetadatos-{marca}.sqlite3"
    respaldo.parent.mkdir(parents=True, exist_ok=True)
    origen = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        destino = sqlite3.connect(str(respaldo))
        try:
            origen.backup(destino)
        finally:
            destino.close()
    finally:
        origen.close()
    registrar(f"  archivo: {respaldo}")
    registrar(f"  sha256 : {sha256(respaldo)}")
    comprobar(radiografia(respaldo) == antes_totales,
              "el backup tiene el mismo contenido que la base")
    if fallas:
        registrar("El backup no quedo bien. No se escribe nada.")
        return 1
    registrar()

    cuando = datetime.now(timezone.utc).replace(microsecond=0)
    registrar("== restauracion ==")
    ctrl = build_comercial_controller(base)
    try:
        for paso in plan:
            # Modificacion parcial: nombra dos campos y deja el resto quieto.
            # Es exactamente la operacion que faltaba cuando se hizo el daño.
            quedo = ctrl.actualizar_articulo(paso["id"], actor=ACTOR, **paso["campos"])
            registrar(f"  {paso['sku']} -> categoria {paso['categoria']!r}, "
                      f"marca {paso['marca']!r}, naturaleza {quedo.nature.value}")
    finally:
        ctrl.close()

    # La bitacora, en su propia conexion y despues de cerrar el controlador:
    # dos conexiones escribiendo a la vez es como se traba SQLite.
    conexion = sqlite3.connect(str(base))
    try:
        for paso in plan:
            conexion.execute(
                "INSERT INTO admin_audit_log(id, actor, action, target_type, target_id,"
                " result, details_json, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid4()), ACTOR, ACCION, "article", paso["id"], "RESTAURADO",
                 json.dumps(dict(
                     sku=paso["sku"],
                     categoria_restaurada=paso["categoria"],
                     marca_restaurada=paso["marca"],
                     fuente=fuente.name,
                     causa=("V1-010 y V1-013 llamaron a guardar_articulo con un "
                            "subconjunto de campos y el reemplazo dejo en blanco "
                            "los que no se nombraron"),
                     alcance="solo category_id y brand_id: nada mas se toco",
                     naturaleza_no_revertida=True),
                     ensure_ascii=False, sort_keys=True),
                 cuando.isoformat()))
        conexion.commit()
    finally:
        conexion.close()
    registrar()

    registrar("== verificacion ==")
    despues_totales = radiografia(base)
    despues_articulos = foto_articulos(base)

    cambios = diferencias(antes_articulos, despues_articulos)
    esperados = {(p["sku"], campo) for p in plan for campo in p["campos"]}
    inesperados = [c for c in cambios if (c[0], c[1]) not in esperados]
    comprobar(not inesperados, f"solo cambiaron los campos autorizados ({inesperados})")
    comprobar(len(cambios) == len(esperados),
              f"cambios: {len(cambios)}, esperados {len(esperados)}")

    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        for sku in AFECTADOS:
            fila = c.execute(
                "SELECT a.sku, a.nature, a.active, ac.name AS categoria, b.name AS marca"
                " FROM articles a"
                " LEFT JOIN article_categories ac ON ac.id=a.category_id"
                " LEFT JOIN brands b ON b.id=a.brand_id WHERE a.sku=?", (sku,)).fetchone()
            comprobar(fila["categoria"] is not None and fila["marca"] is not None,
                      f"{sku}: categoria {fila['categoria']!r}, marca {fila['marca']!r}")
        # Lo que la mision pidio preservar, verificado contra la base y no contra
        # la memoria de nadie.
        limpia = c.execute(
            "SELECT nature FROM articles WHERE sku='000010'").fetchone()["nature"]
        comprobar(limpia == "PRODUCTO_STOCKEABLE", f"000010 sigue siendo {limpia}")
        stock = dict(c.execute(
            "SELECT sa.destination, sa.quantity FROM stock_actual sa JOIN articles a"
            " ON a.id=sa.article_id WHERE a.sku='000010'").fetchall())
        comprobar(stock.get("ASUNCION") == 100 and stock.get("PILAR") == 10,
                  f"000010 stock: {stock}")
        for sku in AFECTADOS[1:]:
            nat = c.execute("SELECT nature FROM articles WHERE sku=?", (sku,)).fetchone()[0]
            comprobar(nat == "SERVICIO_NO_STOCKEABLE", f"{sku} sigue siendo {nat}")
        # La bitacora se compara contra la que habia, no contra numeros
        # supuestos: lo unico que puede aparecer es la accion de esta mision, y
        # las 5 EDITA_ARTICULO que deja el propio guardado.
        ahora = dict(c.execute("SELECT action, COUNT(*) FROM admin_audit_log"
                               " GROUP BY action").fetchall())
        for accion, cuantas in sorted(bitacora_antes.items()):
            esperada = cuantas + (len(plan) if accion == "EDITA_ARTICULO" else 0)
            comprobar(ahora.get(accion) == esperada,
                      f"bitacora {accion}: {cuantas} -> {ahora.get(accion)}"
                      f" (esperado {esperada})")
        aparecidas = set(ahora) - set(bitacora_antes)
        comprobar(aparecidas == {ACCION},
                  f"acciones nuevas en la bitacora: {sorted(aparecidas)}")
        comprobar(ahora.get(ACCION) == len(plan),
                  f"bitacora {ACCION}: {ahora.get(ACCION)} entradas nuevas")
    finally:
        c.close()

    comprobar(despues_totales["movimientos"] == antes_totales["movimientos"],
              f"movimientos sin cambios: {antes_totales['movimientos']}")
    comprobar(despues_totales["asuncion"] == antes_totales["asuncion"]
              and despues_totales["pilar"] == antes_totales["pilar"],
              f"stock sin cambios: ASU {antes_totales['asuncion']} / "
              f"PIL {antes_totales['pilar']}")
    for clave in ("articulos", "activos", "categorias", "marcas",
                  "entradas", "suma_caja", "sale_items"):
        comprobar(despues_totales[clave] == antes_totales[clave],
                  f"{clave} sin cambios: {antes_totales[clave]}")
    for clave, etiqueta in (("integridad", "integrity_check"), ("fk", "foreign_key_check"),
                            ("negativos", "stock negativo"), ("huerfanos", "huerfanos"),
                            ("efectos", "efectos sin hecho")):
        esperado = "ok" if clave == "integridad" else 0
        comprobar(despues_totales[clave] == esperado,
                  f"{etiqueta}: {despues_totales[clave]}")

    registrar()
    registrar(f"sha256 despues: {sha256(base)}")
    registrar(f"VEREDICTO: {'PASS' if not fallas else 'FALLA'} ({len(fallas)} fallas)")
    for falla in fallas:
        registrar(f"  - {falla}")
    if fallas:
        registrar()
        registrar("Para volver atras: cerrar BC Caja, borrar la base con su -wal y "
                  f"-shm, y copiar {respaldo} encima")
    return 0 if not fallas else 1


if __name__ == "__main__":
    raise SystemExit(main())
