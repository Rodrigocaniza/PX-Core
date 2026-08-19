"""Simula la carga inicial del catálogo sobre una COPIA de la base productiva.

Que el archivo esté bien formado no dice nada sobre qué le pasa a la base al
aplicarlo. Este script lo aplica de verdad, con el mecanismo real de dos pasos,
contra una copia consistente: la base real se abre siempre en modo `ro` y sólo
para copiarla.

Verifica lo que importa y no lo da por hecho: que el catálogo no cree stock, que
el inventario inicial entre como hecho auditado con la fecha de su recuento,
que repetirlo no duplique nada, y que Caja quede intacta.

    python tools/carga_inicial_optica_dry_run.py --entrada <dir> [--base <ruta>] [--salida <dir>]
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

CORTES = {"ASUNCION": "2026-08-03", "PILAR": "2026-08-10"}
PLANILLA = {"ASUNCION": "PC - Inventario.xlsx", "PILAR": "P2 - Inventario.xlsx"}

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


def copiar_consistente(origen: Path, destino: Path) -> None:
    """Por la API de backup de SQLite: una copia de archivo dejaría el WAL afuera."""
    destino.unlink(missing_ok=True)
    fuente = sqlite3.connect(f"file:{origen}?mode=ro", uri=True)
    try:
        salida = sqlite3.connect(str(destino))
        try:
            fuente.backup(salida)
        finally:
            salida.close()
    finally:
        fuente.close()


def radiografia(ruta: Path) -> dict:
    conexion = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        def uno(consulta: str):
            return conexion.execute(consulta).fetchone()[0]

        return dict(
            articulos=uno("SELECT COUNT(*) FROM articles"),
            movimientos=uno("SELECT COUNT(*) FROM stock_movements"),
            categorias=uno("SELECT COUNT(*) FROM article_categories"),
            marcas=uno("SELECT COUNT(*) FROM brands"),
            asuncion=uno("SELECT COALESCE(SUM(quantity),0) FROM stock_movements"
                         " WHERE destination='ASUNCION'"),
            pilar=uno("SELECT COALESCE(SUM(quantity),0) FROM stock_movements"
                      " WHERE destination='PILAR'"),
            cash_entries=uno("SELECT COUNT(*) FROM cash_entries"),
            suma_caja=uno("SELECT COALESCE(SUM(total),0) FROM cash_entries"),
            sale_items=uno("SELECT COUNT(*) FROM sale_items"),
            integridad=uno("PRAGMA integrity_check"),
            fk=len(conexion.execute("PRAGMA foreign_key_check").fetchall()),
            negativos=uno("SELECT COUNT(*) FROM stock_actual WHERE quantity < 0"),
            huerfanos=uno("SELECT COUNT(*) FROM stock_movements sm"
                          " LEFT JOIN articles a ON a.id = sm.article_id"
                          " WHERE a.id IS NULL"),
            efectos_sin_hecho=uno("SELECT COUNT(*) FROM event_effects ee"
                                  " LEFT JOIN domain_events de ON de.event_id = ee.event_id"
                                  " WHERE de.event_id IS NULL"),
        )
    finally:
        conexion.close()


PENDIENTE = "STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION"


def anotar_pendientes(base: Path, pendientes: list[dict], por_sku: dict, actor: str) -> None:
    """Deja el estado pendiente como hecho auditado, y verifica que no sea stock.

    El artículo existe y su naturaleza dice que puede llevar unidades; lo que no
    existe es un conteo. La forma canónica de decirlo en este modelo es **no
    escribir el movimiento**: `stock_actual` agrupa movimientos, así que un
    artículo sin ninguno no tiene fila en la vista y `stock_por_destino()`
    devuelve vacío. El sistema no afirma «hay cero»; no afirma nada.

    Lo que sí se escribe es el registro de por qué: la cantidad que la fuente
    declaró queda en `admin_audit_log`, que es la bitácora que ya usa el resto
    del módulo, y en las notas del artículo.
    """
    conexion = sqlite3.connect(str(base))
    try:
        for p in pendientes:
            article_id = por_sku[p["sku"]]
            conexion.execute(
                "INSERT INTO admin_audit_log(id, actor, action, target_type, target_id,"
                " result, details_json, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                (str(uuid4()), actor, PENDIENTE, "article", article_id, "PENDIENTE",
                 json.dumps(p, ensure_ascii=False, sort_keys=True),
                 datetime.now(timezone.utc).replace(microsecond=0).isoformat()))
        conexion.commit()

        anotados = conexion.execute(
            "SELECT COUNT(*) FROM admin_audit_log WHERE action = ?", (PENDIENTE,)).fetchone()[0]
        comprobar(anotados == len(pendientes),
                  f"{anotados} articulos anotados como {PENDIENTE}")
        for p in pendientes:
            article_id = por_sku[p["sku"]]
            # Lo pendiente es la cantidad EN ESA SUCURSAL, no el articulo. 000010
            # es un codigo global: Pilar conto 10 y esos si entran; los 2.860 de
            # Asuncion son los que esperan. El mismo articulo puede tener stock
            # confirmado en un deposito y ninguna afirmacion en el otro.
            movimientos = conexion.execute(
                "SELECT COUNT(*) FROM stock_movements WHERE article_id = ?"
                " AND destination = ?", (article_id, p["sucursal"])).fetchone()[0]
            comprobar(movimientos == 0,
                      f"{p['sku']} {p['nombre'][:24]} en {p['sucursal']}: sin movimiento "
                      f"por sus {p['source_reported_quantity']} declarados")
            filas_en_vista = conexion.execute(
                "SELECT COUNT(*) FROM stock_actual WHERE article_id = ? AND destination = ?",
                (article_id, p["sucursal"])).fetchone()[0]
            comprobar(filas_en_vista == 0,
                      f"{p['sku']} en {p['sucursal']}: no figura en stock_actual -- el sistema "
                      f"no afirma cero, no afirma nada")
            existe = conexion.execute(
                "SELECT nature, notes FROM articles WHERE id = ?", (article_id,)).fetchone()
            comprobar(existe is not None, f"{p['sku']}: el articulo si existe en el catalogo")
            comprobar(PENDIENTE in (existe[1] or ""),
                      f"{p['sku']}: la nota del articulo conserva el estado y la cifra fuente")
        declaradas = sum(p["source_reported_quantity"] or 0 for p in pendientes)
        registrar(f"  ---  {len(pendientes)} articulos, {declaradas} unidades declaradas por "
                  f"la fuente que NO se convirtieron en ledger")
    finally:
        conexion.close()


def desglose(base: Path, recuentos: dict, pendientes: list[dict]) -> None:
    conexion = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        def uno(consulta: str, *args):
            return conexion.execute(consulta, args).fetchone()[0]

        creados = uno("SELECT COUNT(*) FROM articles")
        con_stock = uno("SELECT COUNT(DISTINCT article_id) FROM stock_movements")
        por_naturaleza = dict(conexion.execute(
            "SELECT nature, COUNT(*) FROM articles GROUP BY nature"))
        registrar(f"  articulos creados                          : {creados}")
        registrar(f"  con inventario inicial confirmado          : {con_stock}")
        registrar(f"  stockeables con cantidad PENDIENTE         : {len(pendientes)}")
        registrar(f"  servicios (no llevan stock por naturaleza) : "
                  f"{por_naturaleza.get('SERVICIO_NO_STOCKEABLE', 0)}")
        registrar(f"  trabajos bajo pedido (idem)                : "
                  f"{por_naturaleza.get('TRABAJO_BAJO_PEDIDO', 0)}")
        registrar(f"  productos stockeables                      : "
                  f"{por_naturaleza.get('PRODUCTO_STOCKEABLE', 0)}")
        no_stockeables = (por_naturaleza.get("SERVICIO_NO_STOCKEABLE", 0)
                          + por_naturaleza.get("TRABAJO_BAJO_PEDIDO", 0))
        # Un articulo global puede estar confirmado en un deposito y pendiente en
        # el otro, asi que las dos listas se solapan y hay que descontarlo.
        skus_pendientes = {p["sku"] for p in pendientes}
        pendientes_sin_ningun_stock = sum(
            1 for sku in skus_pendientes
            if uno("SELECT COUNT(*) FROM stock_movements sm JOIN articles a"
                   " ON a.id = sm.article_id WHERE a.sku = ?", sku) == 0)
        solapados = len(skus_pendientes) - pendientes_sin_ningun_stock
        if solapados:
            registrar(f"  de esos pendientes, {solapados} tienen stock confirmado en la otra "
                      f"sucursal (codigo global)")
        comprobar(creados == con_stock + pendientes_sin_ningun_stock + no_stockeables,
                  f"cuadra: {con_stock} con stock + {pendientes_sin_ningun_stock} pendientes "
                  f"sin stock en ningun deposito + {no_stockeables} que no llevan stock "
                  f"= {creados}")
        for sucursal, lineas in recuentos.items():
            registrar(f"  {sucursal:9} CONFIRMED_INITIAL_STOCK: {len(lineas)} lineas, "
                      f"{sum(x['cantidad'] for x in lineas)} unidades")
        for p in pendientes:
            registrar(f"  {p['sucursal']:9} PENDING: {p['sku']} {p['nombre'][:26]:28} "
                      f"la fuente declara {p['source_reported_quantity']}")
    finally:
        conexion.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", required=True,
                        help="directorio con catalogo_canonico.csv y recuento_<SUCURSAL>.json")
    parser.add_argument("--base", default=None, help="por defecto, la base productiva")
    parser.add_argument("--salida", default=None)
    args = parser.parse_args()

    entrada = Path(args.entrada)
    real = Path(args.base) if args.base else Path(resolve_data_paths().database)
    trabajo = Path(args.salida) if args.salida else entrada
    trabajo.mkdir(parents=True, exist_ok=True)
    copia = trabajo / "dry_run.sqlite3"

    catalogo = entrada / "catalogo_canonico.csv"
    recuentos = {s: json.loads((entrada / f"recuento_{s}.json").read_text(encoding="utf-8"))
                 for s in CORTES}
    actor = "COMMAND_CENTER/BC-OPTICA-CARGA-INICIAL-CATALOGO-V1-008 (dry run)"
    corridas_id = {s: f"dryrun-inventario-inicial-{s.lower()}-{CORTES[s].replace('-', '')}"
                   for s in CORTES}
    origen = {s: (f"Inventario inicial {s}: recuento del {CORTES[s]}, planilla "
                  f"{PLANILLA[s]}, cargado por Command Center") for s in CORTES}

    sha_antes = sha256(real)
    registrar("DRY RUN -- CARGA INICIAL DEL CATALOGO SOBRE COPIA DE LA BASE PRODUCTIVA")
    registrar(f"base productiva : {real}")
    registrar(f"sha256 antes    : {sha_antes}")
    copiar_consistente(real, copia)
    registrar(f"copia aislada   : {copia}")
    antes = radiografia(copia)
    registrar(f"antes           : {antes['articulos']} articulos, {antes['movimientos']} "
              f"movimientos, {antes['cash_entries']} entradas de Caja, suma {antes['suma_caja']}")
    registrar()

    controlador = build_comercial_controller(copia)
    try:
        registrar("== paso 1 -- planificar el catalogo (no escribe) ==")
        plan = controlador.planificar_carga_de_articulos(catalogo)
        registrar(f"  archivo : {plan.archivo.name}")
        registrar(f"  sha256  : {plan.file_sha256}")
        registrar(f"  plan    : {plan.resumen}")
        comprobar(plan.aplicable, "el plan no tiene rechazos: es aplicable entero")
        for rechazo in plan.rechazos[:10]:
            registrar(f"      fila {rechazo.fila} sku={rechazo.sku!r}: {rechazo.motivo}")
        registrar()

        registrar("== paso 1b -- aplicar el catalogo (crea articulos, NI UNA unidad) ==")
        corrida = controlador.aplicar_carga_de_articulos(plan, actor=actor)
        tras_catalogo = radiografia(copia)
        registrar(f"  corrida : {corrida.id} ({corrida.result})")
        comprobar(tras_catalogo["articulos"] == len(plan.filas),
                  f"{tras_catalogo['articulos']} articulos creados")
        comprobar(tras_catalogo["movimientos"] == 0,
                  "catalogo no es stock: cero movimientos tras crear el catalogo")
        registrar(f"  categorias: {tras_catalogo['categorias']}, marcas: {tras_catalogo['marcas']}")
        registrar()

        registrar("== paso 2 -- inventario inicial como hecho auditado ==")
        por_sku = {a.sku: a.id for a in controlador.buscar_articulos()}
        comprobar(len(por_sku) == tras_catalogo["articulos"],
                  "todos los articulos se resuelven por SKU")
        corridas = {}
        for sucursal, lineas_recuento in recuentos.items():
            faltantes = [x for x in lineas_recuento if x["sku"] not in por_sku]
            comprobar(not faltantes,
                      f"{sucursal}: todas las lineas del recuento resuelven a un articulo")
            recuento = [(por_sku[x["sku"]], sucursal, x["cantidad"])
                        for x in lineas_recuento if x["sku"] in por_sku]
            corridas[sucursal] = controlador.cargar_stock_inicial(
                recuento, actor=actor, origen=origen[sucursal],
                run_id=corridas_id[sucursal],
                momento=datetime.fromisoformat(CORTES[sucursal]).replace(tzinfo=timezone.utc))
            registrar(f"  {sucursal:9}: {corridas[sucursal].rows_imported} lineas cargadas")
        despues = radiografia(copia)
        registrar()

        registrar("== stock resultante por sucursal ==")
        for sucursal in recuentos:
            esperado = sum(x["cantidad"] for x in recuentos[sucursal])
            comprobar(despues[sucursal.lower()] == esperado,
                      f"{sucursal}: {despues[sucursal.lower()]} unidades (esperado {esperado})")
        comprobar(despues["movimientos"] == sum(len(v) for v in recuentos.values()),
                  f"{despues['movimientos']} movimientos, uno por linea de recuento")
        registrar()

        registrar("== el hecho quedo con origen, causa, actor y fecha ==")
        conexion = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
        try:
            def agrupar(columna: str) -> dict:
                return dict(conexion.execute(
                    f"SELECT {columna}, COUNT(*) FROM stock_movements GROUP BY {columna}"))

            comprobar(agrupar("kind") == {"INGRESO_ADMINISTRATIVO": despues["movimientos"]},
                      "todo entro como INGRESO_ADMINISTRATIVO, ninguna compra falseada")
            comprobar(list(agrupar("reason_code")) == ["INVENTARIO_INICIAL"],
                      "el unico motivo es INVENTARIO_INICIAL")
            comprobar(conexion.execute(
                "SELECT COUNT(*) FROM stock_movements WHERE TRIM(COALESCE(note,'')) = ''"
            ).fetchone()[0] == 0, "ningun movimiento sin explicacion escrita")
            comprobar(conexion.execute(
                "SELECT COUNT(*) FROM stock_movements WHERE TRIM(COALESCE(actor,'')) = ''"
            ).fetchone()[0] == 0, "ningun movimiento sin actor")
            fechas = agrupar("SUBSTR(occurred_at,1,10)")
            registrar(f"  fecha de corte grabada: {fechas}")
            comprobar(set(fechas) == set(CORTES.values()),
                      "cada sucursal quedo con la fecha de su recuento, no con la de hoy")
        finally:
            conexion.close()
        registrar()

        registrar("== idempotencia: repetir exactamente lo mismo ==")
        try:
            controlador.aplicar_carga_de_articulos(
                controlador.planificar_carga_de_articulos(catalogo), actor=actor)
            comprobar(False, "reaplicar el mismo archivo deberia rechazarse por sha256")
        except Exception as error:  # noqa: BLE001 - el mensaje es parte de lo verificado
            comprobar("ya se carg" in str(error),
                      f"reaplicar el mismo archivo se rechaza: {str(error)[:60]}")
        for sucursal, lineas_recuento in recuentos.items():
            otra = controlador.cargar_stock_inicial(
                [(por_sku[x["sku"]], sucursal, x["cantidad"]) for x in lineas_recuento],
                actor=actor, origen=origen[sucursal], run_id=corridas_id[sucursal])
            comprobar(otra.id == corridas[sucursal].id,
                      f"{sucursal}: repetir devuelve la misma corrida, no una nueva")
        repetido = radiografia(copia)
        comprobar(repetido["movimientos"] == despues["movimientos"],
                  f"repetir no duplico movimientos: siguen {repetido['movimientos']}")
        comprobar(repetido["articulos"] == despues["articulos"], "repetir no duplico articulos")
        registrar()

        registrar("== invariantes e integridad ==")
        comprobar(repetido["integridad"] == "ok", f"integrity_check ok ({repetido['integridad']})")
        comprobar(repetido["fk"] == 0, f"foreign_key_check sin violaciones ({repetido['fk']})")
        comprobar(repetido["negativos"] == 0, f"stock negativo: {repetido['negativos']}")
        comprobar(repetido["huerfanos"] == 0, f"movimientos sin articulo: {repetido['huerfanos']}")
        comprobar(repetido["efectos_sin_hecho"] == 0,
                  f"efectos sin hecho: {repetido['efectos_sin_hecho']}")
        registrar()

        registrar("== los datos de Caja no se tocaron ==")
        for clave, etiqueta in (("cash_entries", "entradas de Caja"),
                                ("suma_caja", "dinero registrado"),
                                ("sale_items", "lineas de venta")):
            comprobar(repetido[clave] == antes[clave], f"{etiqueta}: {antes[clave]}")
        registrar()

        pendientes = json.loads(
            (entrada / "pendientes_de_verificacion.json").read_text(encoding="utf-8"))
        registrar("== cantidad pendiente de verificacion fisica ==")
        anotar_pendientes(copia, pendientes, por_sku, actor)
        registrar()

        registrar("== que entro y que no, por clase ==")
        desglose(copia, recuentos, pendientes)
        registrar()
    finally:
        controlador.close()

    sha_despues = sha256(real)
    registrar(f"sha256 base productiva despues: {sha_despues}")
    comprobar(sha_despues == sha_antes,
              "la base productiva quedo intacta: nunca se abrio para escribir")
    registrar()
    registrar(f"VEREDICTO: {'PASS' if not fallas else 'FALLA'} ({len(fallas)} fallas)")
    for falla in fallas:
        registrar(f"  - {falla}")
    (trabajo / "DRY_RUN.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return 0 if not fallas else 1


if __name__ == "__main__":
    raise SystemExit(main())
