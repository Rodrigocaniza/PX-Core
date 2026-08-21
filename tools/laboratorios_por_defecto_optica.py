# -*- coding: utf-8 -*-
"""Da de alta los laboratorios y le pone a cada cristal el suyo por defecto.

La operadora escribe hoy el nombre del laboratorio a mano en cada venta. Por eso
en las diez lineas que existen conviven 'Optilab', 'optilab', 'SI' y 'asasa': el
dato no estaba en ningun lado y habia que acordarse. Esto lo pone donde
corresponde, una vez.

Es una preferencia, no una identidad. No toca una sola venta anterior, no mueve
stock y no convierte ningun laboratorio en marca.

    python tools/laboratorios_por_defecto_optica.py [--base <ruta>] [--confirmar]
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

OPTILAB = "Laboratorio Optilab"
SERVI = "ServiOptica"
CRISTAL = "Laboratorio Cristal"
LABORATORIOS = (OPTILAB, SERVI, CRISTAL)

#: El catalogo tal como lo confirmo el dueno. `None` es explicito: ese cristal
#: no lleva laboratorio por defecto hasta que exista informacion real.
CATALOGO: tuple[tuple[str, str, str | None], ...] = (
    ("2000125", "Futurex Still", SERVI),
    ("2000066", "Multifocal Solamax", OPTILAB),
    ("2000067", "Bifocal (ST)", OPTILAB),
    ("2000124", "Foto Sunsenso", OPTILAB),
    ("2000073", "Multiblue", OPTILAB),
    ("2000075", "Futurex Protec", SERVI),
    ("2000076", "Blue Protec", SERVI),
    ("2000074", "Progresivo OP", OPTILAB),
    ("2000086", "Foto SunActive", OPTILAB),
    ("2000060", "Orgánico UVX", OPTILAB),
    ("2000061", "Fotocromático (AR)", OPTILAB),
    ("2000062", "Multifocal OP o Eclipse", OPTILAB),
    ("2000063", "Kripto (Kto) Orgánico UVX", OPTILAB),
    ("2000064", "Blue Ar", OPTILAB),
    ("2000139", "Blue Light 1.60", SERVI),
    ("2000213", "Org AR", OPTILAB),
    ("2000214", "Kto.Foto.AR", SERVI),
    ("2000215", "Kto.Foto", OPTILAB),
    ("2000216", "Kto.Foto Blue AR", SERVI),
    ("2000217", "Policarbonato Blanco", OPTILAB),
    ("2000218", "Policarbonato AR", OPTILAB),
    ("2000206", "Kto.Invisible", OPTILAB),
    ("2000207", "Kto.AR", OPTILAB),
    ("2000208", "Kto.Blue AR", SERVI),
    ("2000209", "Blue Fotocromatico AR", SERVI),
    ("2000212", "ST Fotocromatico", None),
    ("2000077", "Fotocromatico Blue Ar", OPTILAB),
    ("2000078", "Multiblue Foto Ar", OPTILAB),
    ("2000090", "Fotocromatico AR", OPTILAB),
    ("2000231", "Multifocal Futurex", OPTILAB),
    ("2000235", "Ultradelgado 1.67 AR", OPTILAB),
    ("2000126", "FUTUREX G2", CRISTAL),
)

ALTA_LAB = "LABORATORY_CATALOG_CREATED"
ASIGNA = "DEFAULT_LABORATORY_ASSIGNED"
ACTOR = "COMMAND_CENTER/BC-OPTICA-LABORATORIO-POR-DEFECTO-V1-012"

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
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        salida = {}
        for fila in c.execute("SELECT * FROM articles"):
            d = dict(fila)
            d.pop("updated_at", None)
            salida[d["sku"]] = d
        return salida
    finally:
        c.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=None)
    parser.add_argument("--confirmar", action="store_true")
    args = parser.parse_args()

    base = Path(args.base) if args.base else Path(resolve_data_paths().database)

    registrar("LABORATORIOS Y LABORATORIO POR DEFECTO DE CADA CRISTAL")
    registrar(f"base   : {base}")
    registrar(f"sha256 : {sha256(base)}")

    # La 028 primero: sin la columna no hay nada que leer ni que escribir. Es
    # idempotente y no toca datos, asi que corre igual en el ensayo y en la
    # corrida de verdad, y no depende de que alguien haya abierto la app antes.
    from modulos.caja_diaria.infrastructure.sqlite_repository import (
        SQLiteCashDayRepository,
    )
    SQLiteCashDayRepository(base).close()

    antes_totales = radiografia(base)
    antes_articulos = foto_articulos(base)
    registrar(f"antes  : {antes_totales['articulos']} articulos, "
              f"{antes_totales['movimientos']} movimientos, "
              f"ASU {antes_totales['asuncion']} / PIL {antes_totales['pilar']}")
    registrar()

    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        bitacora_antes = dict(c.execute("SELECT action, COUNT(*) FROM admin_audit_log"
                                        " GROUP BY action").fetchall())
        labs_antes = [dict(r) for r in c.execute(
            "SELECT id, name, active FROM laboratories ORDER BY name")]
        marcas_antes = {
            nombre: c.execute("SELECT COUNT(*) FROM brands WHERE name=? COLLATE NOCASE",
                              (nombre,)).fetchone()[0]
            for nombre in LABORATORIOS}

        registrar("== el catalogo del brief, contra produccion ==")
        plan, ausentes, sin_default, avisos = [], [], [], []
        for sku, nombre_brief, lab in CATALOGO:
            fila = c.execute(
                "SELECT a.id, a.sku, a.name, a.nature, a.active, a.default_laboratory_id,"
                " ac.name AS cat FROM articles a"
                " LEFT JOIN article_categories ac ON ac.id=a.category_id"
                " WHERE a.sku=?", (sku,)).fetchone()
            if fila is None:
                ausentes.append((sku, nombre_brief, lab))
                registrar(f"  {sku:9s} NO EXISTE en produccion -- «{nombre_brief}». "
                          "No se le puede poner laboratorio a algo que no esta")
                continue
            if fila["name"].strip().lower() != nombre_brief.strip().lower():
                avisos.append((sku, nombre_brief, fila["name"]))
            if lab is None:
                sin_default.append((sku, fila["name"], fila["nature"], fila["cat"]))
                registrar(f"  {sku:9s} «{fila['name']}» -- SIN LABORATORIO POR DEFECTO, "
                          "a proposito")
                continue
            plan.append(dict(sku=sku, id=fila["id"], nombre=fila["name"], lab=lab,
                             ya=fila["default_laboratory_id"], nature=fila["nature"],
                             cat=fila["cat"]))
            registrar(f"  {sku:9s} «{fila['name']}» | {fila['nature']} | cat {fila['cat']}"
                      f" -> {lab}")

        registrar()
        if avisos:
            registrar("== el codigo coincide pero el nombre no ==")
            for sku, brief, real in avisos:
                registrar(f"  {sku}: brief «{brief}» / produccion «{real}»")
            registrar("  Se asigna igual: el codigo es la identidad del catalogo y son")
            registrar("  todos cristales activos. Quedan reportados uno por uno.")
            registrar()

        registrar("== cristales de produccion que el brief no menciona ==")
        huerfanos = c.execute(
            "SELECT a.sku, a.name FROM articles a WHERE a.nature='TRABAJO_BAJO_PEDIDO'"
            " AND a.active=1 AND a.sku NOT IN ({})".format(
                ",".join("?" * len(CATALOGO))),
            tuple(s for s, _, _ in CATALOGO)).fetchall()
        for h in huerfanos:
            registrar(f"  {h['sku']:9s} «{h['name']}» -- se queda sin default")
        if not huerfanos:
            registrar("  ninguno")
    finally:
        c.close()
    registrar()

    registrar("== guardas ==")
    comprobar(all(p["nature"] == "TRABAJO_BAJO_PEDIDO" for p in plan),
              "todos los que reciben default son TRABAJO_BAJO_PEDIDO")
    comprobar(not any(p["cat"] != "Cristales" for p in plan),
              "todos estan en la categoria Cristales")
    ya_puestos = [p for p in plan if p["ya"]]
    registrar(f"  ---  ya tenian laboratorio: {len(ya_puestos)} de {len(plan)}")
    if fallas:
        registrar()
        registrar("Alguno no es un cristal. No se escribe nada.")
        return 1
    registrar()

    resumen = {}
    for p in plan:
        resumen[p["lab"]] = resumen.get(p["lab"], 0) + 1
    registrar("== resumen del plan ==")
    for lab in LABORATORIOS:
        registrar(f"  {lab}: {resumen.get(lab, 0)} cristales")
    registrar(f"  sin default a proposito: {len(sin_default)}")
    registrar(f"  del brief pero ausentes de produccion: {len(ausentes)}")
    registrar(f"  cristales de produccion fuera del brief: {len(huerfanos)}")
    registrar()

    if not args.confirmar:
        registrar("NO SE ESCRIBIO NADA: falta --confirmar.")
        registrar(f"Esto crearia o reusaria {len(LABORATORIOS)} laboratorios y pondria "
                  f"el default en {len(plan)} cristales. Cero movimientos de stock.")
        return 0

    registrar("== backup verificable ==")
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    respaldo = base.parent / "Backups" / f"bc-caja-prelaboratorios-{marca}.sqlite3"
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
    creados, asignados = [], []
    ctrl = build_comercial_controller(base)
    try:
        registrar("== laboratorios ==")
        conocidos = {}
        for nombre in LABORATORIOS:
            existia = ctrl._buscar_por_nombre(
                ctrl.listar_laboratorios(solo_activos=False), nombre) is not None
            lab = ctrl.laboratorio_por_nombre(nombre)
            conocidos[nombre] = lab
            registrar(f"  {'reusado ' if existia else 'creado  '} «{lab.name}»  {lab.id}")
            if not existia:
                creados.append(lab)

        registrar()
        registrar("== laboratorio por defecto ==")
        for p in plan:
            objetivo = conocidos[p["lab"]].id
            if p["ya"] == objetivo:
                registrar(f"  {p['sku']:9s} ya estaba en {p['lab']}")
                continue
            ctrl.asignar_laboratorio_por_defecto(p["id"], objetivo, actor=ACTOR)
            registrar(f"  {p['sku']:9s} «{p['nombre']}» -> {p['lab']}")
            asignados.append(p)
    finally:
        ctrl.close()

    conexion = sqlite3.connect(str(base))
    try:
        for lab in creados:
            conexion.execute(
                "INSERT INTO admin_audit_log(id, actor, action, target_type, target_id,"
                " result, details_json, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid4()), ACTOR, ALTA_LAB, "laboratory", lab.id, "CREADO",
                 json.dumps(dict(nombre=lab.name,
                                 catalogo="laboratories, el mismo del seguimiento",
                                 nota="no se creo un segundo catalogo de laboratorios"),
                            ensure_ascii=False, sort_keys=True),
                 cuando.isoformat()))
        for p in asignados:
            conexion.execute(
                "INSERT INTO admin_audit_log(id, actor, action, target_type, target_id,"
                " result, details_json, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid4()), ACTOR, ASIGNA, "article", p["id"], "ASIGNADO",
                 json.dumps(dict(sku=p["sku"], nombre=p["nombre"], laboratorio=p["lab"],
                                 es_preferencia_no_identidad=True,
                                 reescribe_ventas_anteriores=False,
                                 editable_por_venta=True),
                            ensure_ascii=False, sort_keys=True),
                 cuando.isoformat()))
        conexion.commit()
    finally:
        conexion.close()
    registrar()

    registrar("== verificacion ==")
    despues_totales = radiografia(base)
    despues_articulos = foto_articulos(base)

    cambiados = []
    for sku, a in antes_articulos.items():
        d = despues_articulos.get(sku)
        for campo in a:
            if a[campo] != d[campo]:
                cambiados.append((sku, campo))
    esperados = {(p["sku"], "default_laboratory_id") for p in asignados}
    inesperados = [x for x in cambiados if x not in esperados]
    comprobar(not inesperados, f"solo cambio default_laboratory_id ({inesperados})")

    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        for nombre in LABORATORIOS:
            n = c.execute("SELECT COUNT(*) FROM laboratories WHERE name=? COLLATE NOCASE",
                          (nombre,)).fetchone()[0]
            comprobar(n == 1, f"«{nombre}»: {n} fila")
        comprobar(c.execute("SELECT COUNT(*) FROM laboratories").fetchone()[0]
                  == len(labs_antes) + len(creados),
                  f"laboratorios: {len(labs_antes)} -> "
                  f"{c.execute('SELECT COUNT(*) FROM laboratories').fetchone()[0]}")
        for p in plan:
            fila = c.execute(
                "SELECT l.name FROM articles a JOIN laboratories l"
                " ON l.id=a.default_laboratory_id WHERE a.sku=?", (p["sku"],)).fetchone()
            comprobar(fila is not None and fila["name"] == p["lab"],
                      f"{p['sku']}: default {fila['name'] if fila else None}")
        for sku, *_ in sin_default:
            fila = c.execute("SELECT default_laboratory_id FROM articles WHERE sku=?",
                             (sku,)).fetchone()
            comprobar(fila["default_laboratory_id"] is None,
                      f"{sku}: sigue sin laboratorio por defecto")
        # Ningun laboratorio se convirtio en marca POR ESTA MISION. Ojo: dos de
        # ellos ya eran marca antes, porque en las planillas de la Optica la
        # columna «Marca» de un cristal trae el laboratorio y asi entro al
        # catalogo. Eso es anterior y se reporta aparte; lo que se verifica aca
        # es que esta mision no agrego ni una marca mas.
        for nombre, antes_marca in marcas_antes.items():
            n = c.execute("SELECT COUNT(*) FROM brands WHERE name=? COLLATE NOCASE",
                          (nombre,)).fetchone()[0]
            comprobar(n == antes_marca,
                      f"«{nombre}» como marca: {antes_marca} -> {n}"
                      + (" (ya venia de la carga inicial)" if antes_marca else ""))
        comprobar(c.execute("SELECT COUNT(*) FROM brands").fetchone()[0]
                  == antes_totales["marcas"],
                  f"marcas sin cambios: {antes_totales['marcas']}")
        # Ni una linea de venta reescrita.
        for r in c.execute("SELECT laboratory, COUNT(*) n FROM sale_items"
                           " GROUP BY laboratory ORDER BY laboratory"):
            registrar(f"  ---  sale_items.laboratory {r['laboratory']!r}: {r['n']}")
        ahora = dict(c.execute("SELECT action, COUNT(*) FROM admin_audit_log"
                               " GROUP BY action").fetchall())
        for accion, cuantas in sorted(bitacora_antes.items()):
            esperada = cuantas + (len(asignados) if accion == "EDITA_ARTICULO" else 0)
            comprobar(ahora.get(accion) == esperada,
                      f"bitacora {accion}: {cuantas} -> {ahora.get(accion)}")
        nuevas = set(ahora) - set(bitacora_antes)
        comprobar(nuevas <= {ALTA_LAB, ASIGNA},
                  f"acciones nuevas: {sorted(nuevas)}")
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
