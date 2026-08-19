"""Cierra los stocks iniciales que quedaron esperando un conteo físico.

La misión anterior creó artículos que existen y no tienen unidades, porque la
cifra que traía la planilla no era un conteo. Este script hace las dos mitades
de resolverlo:

`--listar` saca de la base quiénes son —no de una lista escrita a mano— y arma la
planilla de conteo. `--aplicar` toma las cantidades contadas y las asienta como
lo que son: un recuento hecho hoy, con la fecha de hoy, que no reescribe ni borra
la cifra vieja sino que la deja al lado para que se pueda comparar.

    python tools/recuento_pendientes_optica.py --listar [--base <ruta>]
    python tools/recuento_pendientes_optica.py --aplicar <conteo.json> [--base <ruta>] [--confirmar]
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
CONFIRMADO = "PHYSICAL_COUNT_CONFIRMED"
ACTOR = "COMMAND_CENTER/BC-OPTICA-RECUENTO-FISICO-PENDIENTES-V1-009"

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


def pendientes(base: Path) -> list[dict]:
    """Quiénes esperan un conteo, según la base. No hay lista escrita a mano.

    Un pendiente que ya se cerró tiene su fila de `PHYSICAL_COUNT_CONFIRMED`, así
    que se lo descuenta acá y no en la cabeza de nadie.
    """
    conexion = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    conexion.row_factory = sqlite3.Row
    try:
        abiertos = []
        for fila in conexion.execute(
                "SELECT al.target_id, al.details_json, al.recorded_at, a.sku, a.name,"
                " a.nature FROM admin_audit_log al JOIN articles a ON a.id = al.target_id"
                " WHERE al.action = ? ORDER BY a.sku", (PENDIENTE,)):
            detalle = json.loads(fila["details_json"])
            sucursal = detalle["sucursal"]
            cerrado = conexion.execute(
                "SELECT COUNT(*) FROM admin_audit_log WHERE action = ? AND target_id = ?"
                " AND json_extract(details_json,'$.sucursal') = ?",
                (CONFIRMADO, fila["target_id"], sucursal)).fetchone()[0]
            if cerrado:
                continue
            movimientos = conexion.execute(
                "SELECT COUNT(*), COALESCE(SUM(quantity),0) FROM stock_movements"
                " WHERE article_id = ? AND destination = ?",
                (fila["target_id"], sucursal)).fetchone()
            otras = dict(conexion.execute(
                "SELECT destination, SUM(quantity) FROM stock_movements WHERE article_id = ?"
                " GROUP BY destination", (fila["target_id"],)))
            abiertos.append(dict(
                article_id=fila["target_id"], sku=fila["sku"], nombre=fila["name"],
                nature=fila["nature"], sucursal=sucursal,
                source_reported_quantity=detalle.get("source_reported_quantity"),
                motivo=detalle.get("motivo", ""), fuente=detalle.get("fuente", ""),
                corte=detalle.get("corte", ""), anotado_el=fila["recorded_at"],
                movimientos_en_esa_sucursal=movimientos[0],
                unidades_en_esa_sucursal=movimientos[1],
                unidades_en_otras_sucursales={k: v for k, v in otras.items() if k != sucursal}))
        return abiertos
    finally:
        conexion.close()


def listar(base: Path, salida: Path | None) -> int:
    abiertos = pendientes(base)
    registrar("PENDIENTES DE CONTEO FISICO, SEGUN LA BASE PRODUCTIVA")
    registrar(f"base: {base}")
    registrar(f"sha256: {sha256(base)}")
    registrar()
    comprobar(bool(abiertos), f"{len(abiertos)} articulos esperan conteo")
    for p in abiertos:
        registrar(f"  {p['sucursal']:9} {p['sku']:>8}  {p['nombre'][:34]:36} "
                  f"nature={p['nature']}")
        registrar(f"      la fuente declaraba : {p['source_reported_quantity']}")
        registrar(f"      origen              : {p['fuente']} (corte {p['corte']})")
        comprobar(p["movimientos_en_esa_sucursal"] == 0,
                  f"{p['sku']} en {p['sucursal']}: sigue sin movimiento "
                  f"({p['movimientos_en_esa_sucursal']})")
        if p["unidades_en_otras_sucursales"]:
            registrar(f"      OJO: en otra sucursal ya tiene "
                      f"{p['unidades_en_otras_sucursales']} -- no se toca")
    if salida:
        plantilla = [dict(sku=p["sku"], sucursal=p["sucursal"], nombre=p["nombre"],
                          source_reported_quantity=p["source_reported_quantity"],
                          cantidad_fisica=None) for p in abiertos]
        salida.write_text(json.dumps(plantilla, ensure_ascii=False, indent=1), encoding="utf-8")
        registrar()
        registrar(f"planilla de conteo: {salida}")
    return 0 if not fallas else 1


def _radiografia(base: Path) -> dict:
    conexion = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        def uno(consulta: str, *args):
            return conexion.execute(consulta, args).fetchone()[0]

        return dict(
            articulos=uno("SELECT COUNT(*) FROM articles"),
            movimientos=uno("SELECT COUNT(*) FROM stock_movements"),
            asuncion=uno("SELECT COALESCE(SUM(quantity),0) FROM stock_movements"
                         " WHERE destination='ASUNCION'"),
            pilar=uno("SELECT COALESCE(SUM(quantity),0) FROM stock_movements"
                      " WHERE destination='PILAR'"),
            pendientes=uno("SELECT COUNT(*) FROM admin_audit_log WHERE action=?", PENDIENTE),
            cerrados=uno("SELECT COUNT(*) FROM admin_audit_log WHERE action=?", CONFIRMADO),
            entradas=uno("SELECT COUNT(*) FROM cash_entries"),
            suma_caja=uno("SELECT COALESCE(SUM(total),0) FROM cash_entries"),
            sale_items=uno("SELECT COUNT(*) FROM sale_items"),
            cash_days=uno("SELECT COUNT(*) FROM cash_days"),
            orders=uno("SELECT COUNT(*) FROM orders"),
            integridad=uno("PRAGMA integrity_check"),
            fk=len(conexion.execute("PRAGMA foreign_key_check").fetchall()),
            negativos=uno("SELECT COUNT(*) FROM stock_actual WHERE quantity < 0"),
            huerfanos=uno("SELECT COUNT(*) FROM stock_movements sm"
                          " LEFT JOIN articles a ON a.id = sm.article_id WHERE a.id IS NULL"),
            efectos=uno("SELECT COUNT(*) FROM event_effects ee LEFT JOIN domain_events de"
                        " ON de.event_id = ee.event_id WHERE de.event_id IS NULL"))
    finally:
        conexion.close()


def _cerrado(base: Path, clave: tuple[str, str]) -> bool:
    """¿Este (sucursal, sku) ya tiene su conteo asentado?"""
    sucursal, sku = clave
    conexion = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        return conexion.execute(
            "SELECT COUNT(*) FROM admin_audit_log al JOIN articles a ON a.id = al.target_id"
            " WHERE a.sku = ? AND al.action = ?"
            " AND json_extract(al.details_json,'$.sucursal') = ?",
            (sku, CONFIRMADO, sucursal)).fetchone()[0] > 0
    finally:
        conexion.close()


def aplicar(base: Path, conteo: Path, confirmar: bool, momento: datetime | None = None) -> int:
    """Asienta los conteos. La cifra vieja no se toca: queda al lado de la nueva."""
    contados = {(x["sucursal"], x["sku"]): x for x in
                json.loads(conteo.read_text(encoding="utf-8"))}
    abiertos = {(p["sucursal"], p["sku"]): p for p in pendientes(base)}

    registrar("RECUENTO FISICO -- APLICACION")
    registrar(f"base   : {base}")
    registrar(f"sha256 : {sha256(base)}")
    registrar(f"conteo : {conteo.name}")
    registrar()

    registrar("== el conteo corresponde a lo que la base dice que falta ==")
    ya_cerrados = sorted(k for k in contados if k not in abiertos and _cerrado(base, k))
    desconocidos = sorted(k for k in contados if k not in abiertos and k not in ya_cerrados)
    if ya_cerrados and not desconocidos and len(ya_cerrados) == len(contados):
        # Reaplicar un conteo ya asentado no es un error: es que no hay nada que
        # hacer. Distinguirlo importa, porque la evidencia de una corrida
        # idempotente no deberia leerse como una falla.
        registrar(f"  ---  los {len(ya_cerrados)} ya estaban cerrados. Nada que asentar")
        registrar("NO SE ESCRIBE NADA: el recuento ya se habia aplicado")
        return 0
    for clave in ya_cerrados:
        registrar(f"  ---  {clave[1]} en {clave[0]} ya estaba cerrado, se omite")
    comprobar(not desconocidos,
              f"todo lo contado es un pendiente conocido ({desconocidos} sin reconocer)")
    for clave in ya_cerrados:
        contados.pop(clave)
    sin_contar = sorted(set(abiertos) - set(contados))
    if sin_contar:
        registrar(f"  ---  quedan sin contar, y siguen pendientes: {sin_contar}")
    for clave, x in contados.items():
        cantidad = x.get("cantidad_fisica")
        comprobar(isinstance(cantidad, int) and cantidad >= 0,
                  f"{clave[1]} en {clave[0]}: cantidad fisica valida ({cantidad!r})")
    if fallas:
        registrar()
        registrar("El conteo no es aplicable. NO se escribe nada.")
        return 1

    cuando = momento or datetime.now(timezone.utc).replace(microsecond=0)
    fecha = cuando.date().isoformat()
    registrar()
    registrar(f"== lo que se asentaria, con fecha de HOY ({fecha}) ==")
    for clave, x in sorted(contados.items()):
        p = abiertos[clave]
        cantidad = x["cantidad_fisica"]
        gesto = ("un movimiento de {} unidades".format(cantidad) if cantidad > 0
                 else "NINGUN movimiento: se registra que se conto y dio cero")
        registrar(f"  {clave[0]:9} {clave[1]:>8} {p['nombre'][:28]:30} "
                  f"fuente decia {p['source_reported_quantity']:>6} -> contado {cantidad:>6}"
                  f"  ({gesto})")
    if not confirmar:
        registrar()
        registrar("NO SE ESCRIBIO NADA: falta --confirmar.")
        return 0

    registrar()
    registrar("== backup verificable, antes de tocar nada ==")
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    respaldo = base.parent / "Backups" / f"bc-caja-prerecuento-{marca}.sqlite3"
    respaldo.parent.mkdir(parents=True, exist_ok=True)
    fuente = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        destino_bk = sqlite3.connect(str(respaldo))
        try:
            fuente.backup(destino_bk)
        finally:
            destino_bk.close()
    finally:
        fuente.close()
    registrar(f"  backup : {respaldo}")
    registrar(f"  sha256 : {sha256(respaldo)}")
    antes = _radiografia(base)
    comprobar(_radiografia(respaldo) == antes, "el backup tiene los mismos datos que la base")
    if fallas:
        registrar("El backup no quedo bien. NO se escribe nada.")
        return 1

    controlador = build_comercial_controller(base)
    try:
        registrar()
        registrar("== asentando ==")
        for clave, x in sorted(contados.items()):
            sucursal, sku = clave
            p = abiertos[clave]
            cantidad = x["cantidad_fisica"]
            corrida = f"recuento-fisico-{sku}-{sucursal.lower()}-{fecha.replace('-', '')}"
            if cantidad > 0:
                # El hecho es el recuento de hoy, no la planilla vieja: por eso la
                # fecha es la de hoy y el motivo sigue siendo INVENTARIO_INICIAL,
                # que es lo que realmente es -- la primera vez que este articulo
                # tiene unidades.
                hecho = controlador.cargar_stock_inicial(
                    [(p["article_id"], sucursal, cantidad)], actor=ACTOR,
                    origen=(f"Recuento fisico del {fecha} en {sucursal}, articulo {sku} "
                            f"{p['nombre']}. La planilla anterior declaraba "
                            f"{p['source_reported_quantity']} y no se habia asentado por no "
                            f"ser un conteo"),
                    run_id=corrida, momento=cuando)
                registrar(f"  {sku} en {sucursal}: {hecho.rows_imported} movimiento, "
                          f"corrida {corrida}")
            else:
                registrar(f"  {sku} en {sucursal}: contado y dio cero. Sin movimiento, "
                          f"porque no hubo nada que ingresar")
        # El cierre del pendiente es un hecho en si mismo, exista o no movimiento.
        # Contar y que de cero NO es lo mismo que no haber contado nunca, y esta
        # fila es lo unico que distingue las dos cosas.
        conexion = sqlite3.connect(str(base))
        try:
            for clave, x in sorted(contados.items()):
                sucursal, sku = clave
                p = abiertos[clave]
                detalle = dict(
                    sku=sku, nombre=p["nombre"], sucursal=sucursal,
                    source_reported_quantity=p["source_reported_quantity"],
                    physical_count=x["cantidad_fisica"],
                    contado_el=fecha,
                    cierra=PENDIENTE,
                    fuente_anterior=p["fuente"], corte_anterior=p["corte"],
                    movimiento_creado=bool(x["cantidad_fisica"] > 0),
                    run_id=(f"recuento-fisico-{sku}-{sucursal.lower()}-"
                            f"{fecha.replace('-', '')}") if x["cantidad_fisica"] > 0 else None)
                conexion.execute(
                    "INSERT INTO admin_audit_log(id, actor, action, target_type, target_id,"
                    " result, details_json, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
                    (str(uuid4()), ACTOR, CONFIRMADO, "article", p["article_id"],
                     "CONFIRMADO", json.dumps(detalle, ensure_ascii=False, sort_keys=True),
                     cuando.isoformat()))
            conexion.commit()
        finally:
            conexion.close()
        registrar(f"  {len(contados)} pendientes cerrados como {CONFIRMADO}")
    finally:
        controlador.close()

    registrar()
    registrar("== verificacion post-escritura ==")
    despues = _radiografia(base)
    positivos = {k: v for k, v in contados.items() if v["cantidad_fisica"] > 0}
    comprobar(despues["movimientos"] == antes["movimientos"] + len(positivos),
              f"{despues['movimientos'] - antes['movimientos']} movimientos nuevos, "
              f"uno por cada cantidad mayor que cero ({len(positivos)})")
    for sucursal in ("ASUNCION", "PILAR"):
        suma = sum(v["cantidad_fisica"] for k, v in contados.items() if k[0] == sucursal)
        clave = sucursal.lower()
        comprobar(despues[clave] == antes[clave] + suma,
                  f"{sucursal}: {antes[clave]} -> {despues[clave]} (+{suma})")
    comprobar(despues["cerrados"] == antes["cerrados"] + len(contados),
              f"{len(contados)} pendientes cerrados")
    comprobar(despues["pendientes"] == antes["pendientes"],
              "las filas de PENDIENTE siguen ahi: la historia no se borra")
    for clave, etiqueta in (("integridad", "integrity_check"), ("fk", "foreign_key_check"),
                            ("negativos", "stock negativo"), ("huerfanos", "huerfanos"),
                            ("efectos", "efectos sin hecho")):
        esperado = "ok" if clave == "integridad" else 0
        comprobar(despues[clave] == esperado, f"{etiqueta}: {despues[clave]}")
    for clave in ("entradas", "suma_caja", "sale_items", "cash_days", "orders"):
        comprobar(despues[clave] == antes[clave], f"Caja, {clave} sin cambios: {antes[clave]}")
    registrar()
    registrar(f"sha256 base despues: {sha256(base)}")
    if fallas:
        registrar()
        registrar("EL RECUENTO NO QUEDO LIMPIO. Para volver atras:")
        registrar("  1. cerrar BC Caja")
        registrar(f"  2. borrar {base.name}, {base.name}-wal y {base.name}-shm")
        registrar(f"  3. copiar {respaldo} sobre {base}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=None)
    parser.add_argument("--listar", action="store_true")
    parser.add_argument("--plantilla", default=None)
    parser.add_argument("--aplicar", default=None)
    parser.add_argument("--confirmar", action="store_true")
    parser.add_argument("--salida", default=None)
    args = parser.parse_args()

    base = Path(args.base) if args.base else Path(resolve_data_paths().database)
    if args.listar:
        codigo = listar(base, Path(args.plantilla) if args.plantilla else None)
    elif args.aplicar:
        codigo = aplicar(base, Path(args.aplicar), args.confirmar)
    else:
        parser.error("hace falta --listar o --aplicar")
    registrar()
    registrar(f"VEREDICTO: {'PASS' if not fallas else 'FALLA'} ({len(fallas)} fallas)")
    for falla in fallas:
        registrar(f"  - {falla}")
    if args.salida:
        Path(args.salida).write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return codigo


if __name__ == "__main__":
    raise SystemExit(main())
