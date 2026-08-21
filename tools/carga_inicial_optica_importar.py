"""Importa el catálogo y el inventario inicial SOBRE LA BASE PRODUCTIVA.

Este es el único script de la misión que escribe en producción, y no corre sin
`--confirmar`. Antes de tocar nada hace el backup por la API de backup de SQLite
y deja su sha256; si cualquier paso falla, se detiene y dice con qué comando se
vuelve atrás.

La secuencia es la misma que el dry-run ejercitó sobre una copia, en el mismo
orden y con los mismos `run_id`, así que repetirla no duplica nada:

    1. backup verificable + hash de la base
    2. paso 1  -- planificar el catálogo (no escribe)
    3. paso 1b -- aplicar el catálogo: crea artículos, ni una unidad
    4. paso 2  -- inventario inicial por sucursal, con la fecha de cada recuento
    5. anotar en la bitácora los artículos con cantidad pendiente
    6. verificación post-import
    7. hash final

    python tools/carga_inicial_optica_importar.py --entrada <dir> --confirmar
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
CORRIDAS = {"ASUNCION": "inventario-inicial-asuncion-20260803",
            "PILAR": "inventario-inicial-pilar-20260810"}
PENDIENTE = "STOCK_INITIAL_PENDING_PHYSICAL_VERIFICATION"
ACTOR = "COMMAND_CENTER/BC-OPTICA-CARGA-INICIAL-CATALOGO-V1-008"

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


def respaldar(real: Path) -> Path:
    """Backup por la API de backup de SQLite: una copia de archivo perdería el WAL."""
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = real.parent / "Backups" / f"bc-caja-preimport-catalogo-{marca}.sqlite3"
    destino.parent.mkdir(parents=True, exist_ok=True)
    fuente = sqlite3.connect(f"file:{real}?mode=ro", uri=True)
    try:
        salida = sqlite3.connect(str(destino))
        try:
            fuente.backup(salida)
        finally:
            salida.close()
    finally:
        fuente.close()
    return destino


def radiografia(ruta: Path) -> dict:
    conexion = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        def uno(consulta: str):
            return conexion.execute(consulta).fetchone()[0]

        return dict(
            articulos=uno("SELECT COUNT(*) FROM articles"),
            movimientos=uno("SELECT COUNT(*) FROM stock_movements"),
            asuncion=uno("SELECT COALESCE(SUM(quantity),0) FROM stock_movements"
                         " WHERE destination='ASUNCION'"),
            pilar=uno("SELECT COALESCE(SUM(quantity),0) FROM stock_movements"
                      " WHERE destination='PILAR'"),
            cash_entries=uno("SELECT COUNT(*) FROM cash_entries"),
            suma_caja=uno("SELECT COALESCE(SUM(total),0) FROM cash_entries"),
            sale_items=uno("SELECT COUNT(*) FROM sale_items"),
            cash_days=uno("SELECT COUNT(*) FROM cash_days"),
            orders=uno("SELECT COUNT(*) FROM orders"),
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


def como_volver_atras(real: Path, backup: Path) -> None:
    registrar()
    registrar("COMO VOLVER ATRAS:")
    registrar("  1. cerrar BC Caja")
    registrar(f"  2. borrar {real.name}, {real.name}-wal y {real.name}-shm")
    registrar(f"  3. copiar {backup} sobre {real}")
    registrar("  4. abrir BC Caja: vuelve al estado exacto de antes de importar")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entrada", required=True)
    parser.add_argument("--base", default=None)
    parser.add_argument("--confirmar", action="store_true",
                        help="sin esto no se escribe nada en produccion")
    args = parser.parse_args()

    entrada = Path(args.entrada)
    real = Path(args.base) if args.base else Path(resolve_data_paths().database)
    catalogo = entrada / "catalogo_canonico.csv"
    recuentos = {s: json.loads((entrada / f"recuento_{s}.json").read_text(encoding="utf-8"))
                 for s in CORTES}
    pendientes = json.loads(
        (entrada / "pendientes_de_verificacion.json").read_text(encoding="utf-8"))

    registrar("IMPORTACION PRODUCTIVA -- CATALOGO E INVENTARIO INICIAL DE LA OPTICA")
    registrar(f"base productiva : {real}")
    antes = radiografia(real)
    registrar(f"antes           : {antes['articulos']} articulos, {antes['movimientos']} "
              f"movimientos, {antes['cash_entries']} entradas de Caja")

    if not args.confirmar:
        registrar()
        registrar("NO SE ESCRIBIO NADA: falta --confirmar.")
        registrar("Esto es lo que haria:")
        registrar(f"  crear {sum(1 for _ in catalogo.open(encoding='utf-8-sig')) - 1} articulos")
        for sucursal, lista in recuentos.items():
            registrar(f"  cargar {sucursal}: {len(lista)} lineas, "
                      f"{sum(x['cantidad'] for x in lista)} unidades, corte {CORTES[sucursal]}")
        registrar(f"  anotar {len(pendientes)} articulos como {PENDIENTE}")
        return 0

    registrar()
    registrar("== backup verificable, antes de tocar nada ==")
    sha_antes = sha256(real)
    backup = respaldar(real)
    registrar(f"  base sha256 antes : {sha_antes}")
    registrar(f"  backup            : {backup}")
    registrar(f"  backup sha256     : {sha256(backup)}")
    respaldo = radiografia(backup)
    comprobar(respaldo["cash_entries"] == antes["cash_entries"]
              and respaldo["suma_caja"] == antes["suma_caja"]
              and respaldo["sale_items"] == antes["sale_items"],
              "el backup tiene los mismos datos que la base")
    comprobar(respaldo["integridad"] == "ok", "el backup pasa integrity_check")
    if fallas:
        registrar("El backup no quedo bien. NO se importa nada.")
        return 1

    controlador = build_comercial_controller(real)
    try:
        registrar()
        registrar("== paso 1b -- catalogo (crea articulos, ni una unidad) ==")
        plan = controlador.planificar_carga_de_articulos(catalogo)
        comprobar(plan.aplicable, f"plan aplicable: {plan.resumen}")
        if not plan.aplicable:
            como_volver_atras(real, backup)
            return 1
        corrida = controlador.aplicar_carga_de_articulos(plan, actor=ACTOR)
        registrar(f"  corrida: {corrida.id} ({corrida.result}), "
                  f"{corrida.rows_imported} articulos")
        intermedio = radiografia(real)
        comprobar(intermedio["movimientos"] == antes["movimientos"],
                  "el catalogo no creo una sola unidad de stock")

        registrar()
        registrar("== paso 2 -- inventario inicial por sucursal ==")
        por_sku = {a.sku: a.id for a in controlador.buscar_articulos()}
        for sucursal, lista in recuentos.items():
            faltantes = [x for x in lista if x["sku"] not in por_sku]
            comprobar(not faltantes, f"{sucursal}: todas las lineas resuelven a un articulo")
            hecho = controlador.cargar_stock_inicial(
                [(por_sku[x["sku"]], sucursal, x["cantidad"]) for x in lista],
                actor=ACTOR,
                origen=(f"Inventario inicial {sucursal}: recuento del {CORTES[sucursal]}, "
                        f"planilla {PLANILLA[sucursal]}, cargado por Command Center"),
                run_id=CORRIDAS[sucursal],
                momento=datetime.fromisoformat(CORTES[sucursal]).replace(tzinfo=timezone.utc))
            registrar(f"  {sucursal:9}: {hecho.rows_imported} lineas, corte {CORTES[sucursal]}")

        registrar()
        registrar("== cantidad pendiente de verificacion fisica ==")
        conexion = sqlite3.connect(str(real))
        try:
            for p in pendientes:
                conexion.execute(
                    "INSERT INTO admin_audit_log(id, actor, action, target_type, target_id,"
                    " result, details_json, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                    (str(uuid4()), ACTOR, PENDIENTE, "article", por_sku[p["sku"]], "PENDIENTE",
                     json.dumps(p, ensure_ascii=False, sort_keys=True),
                     datetime.now(timezone.utc).replace(microsecond=0).isoformat()))
            conexion.commit()
        finally:
            conexion.close()
        registrar(f"  {len(pendientes)} articulos anotados; sus "
                  f"{sum(p['source_reported_quantity'] or 0 for p in pendientes)} unidades "
                  f"declaradas NO entraron al ledger")
    finally:
        controlador.close()

    registrar()
    registrar("== verificacion post-import ==")
    despues = radiografia(real)
    esperado = {s: sum(x["cantidad"] for x in recuentos[s]) for s in recuentos}
    comprobar(despues["asuncion"] == esperado["ASUNCION"],
              f"ASUNCION: {despues['asuncion']} unidades (esperado {esperado['ASUNCION']})")
    comprobar(despues["pilar"] == esperado["PILAR"],
              f"PILAR: {despues['pilar']} unidades (esperado {esperado['PILAR']})")
    comprobar(despues["movimientos"] == sum(len(v) for v in recuentos.values()),
              f"{despues['movimientos']} movimientos, uno por linea")
    comprobar(despues["integridad"] == "ok", "integrity_check ok")
    comprobar(despues["fk"] == 0, "foreign_key_check sin violaciones")
    comprobar(despues["negativos"] == 0, "sin stock negativo")
    comprobar(despues["huerfanos"] == 0, "sin movimientos huerfanos")
    comprobar(despues["efectos_sin_hecho"] == 0, "sin efectos sin hecho")
    for clave, etiqueta in (("cash_entries", "entradas de Caja"), ("suma_caja", "dinero"),
                            ("sale_items", "lineas de venta"), ("cash_days", "dias"),
                            ("orders", "pedidos")):
        comprobar(despues[clave] == antes[clave], f"{etiqueta} sin cambios: {antes[clave]}")

    registrar()
    registrar(f"base sha256 despues: {sha256(real)}")
    registrar(f"VEREDICTO: {'PASS' if not fallas else 'FALLA'} ({len(fallas)} fallas)")
    for falla in fallas:
        registrar(f"  - {falla}")
    if fallas:
        registrar()
        registrar("LA IMPORTACION NO QUEDO LIMPIA.")
        como_volver_atras(real, backup)
    (entrada / "IMPORT_PRODUCTIVO.txt").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return 0 if not fallas else 1


if __name__ == "__main__":
    raise SystemExit(main())
