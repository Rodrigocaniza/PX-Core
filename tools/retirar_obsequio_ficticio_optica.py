"""Retira `000037 LIMPIA CRISTAL OBSEQUIO`, el artículo inventado del regalo.

Sus unidades no representan frascos: representan la ficción de un producto que
existía sólo para poder poner precio cero. Por eso no se trasladan a `000010` ni
a ningún otro artículo — se compensan a cero y se apagan.

El orden importa y no es negociable: primero el stock a cero, después el retiro.
Un artículo inactivo con unidades encima es stock que nadie mira.

    python tools/retirar_obsequio_ficticio_optica.py [--base <ruta>] [--confirmar]
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
from modulos.comercial.domain.models import (  # noqa: E402
    Destination, StockMovement, StockMovementKind,
)

SKU_FICTICIO = "000037"
SKU_REAL = "000010"
MOTIVO = "ERROR_INVENTARIO"
CAUSA = "RECONCILIACION_STOCK_FICTICIO / PROMO_OBSEQUIO_LEGACY"
RETIRO = "PROMO_OBSEQUIO_LEGACY_RETIRED"
ACTOR = "COMMAND_CENTER/BC-OPTICA-PROMO-LIMPIA-CRISTAL-V1-013"

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
            stock_en_retirados=q("SELECT COUNT(*) FROM stock_actual sa JOIN articles a"
                                 " ON a.id=sa.article_id WHERE a.active=0 AND sa.quantity<>0"),
        )
    finally:
        c.close()


def stock_por_sucursal(base: Path, sku: str) -> dict:
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        return dict(c.execute(
            "SELECT sm.destination, SUM(sm.quantity) FROM stock_movements sm"
            " JOIN articles a ON a.id=sm.article_id WHERE a.sku=? GROUP BY sm.destination",
            (sku,)))
    finally:
        c.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=None)
    parser.add_argument("--confirmar", action="store_true")
    args = parser.parse_args()

    base = Path(args.base) if args.base else Path(resolve_data_paths().database)
    antes = radiografia(base)
    ficticio = stock_por_sucursal(base, SKU_FICTICIO)
    real = stock_por_sucursal(base, SKU_REAL)

    registrar("RETIRO DEL OBSEQUIO FICTICIO")
    registrar(f"base   : {base}")
    registrar(f"sha256 : {sha256(base)}")
    registrar()
    registrar(f"  {SKU_FICTICIO} LIMPIA CRISTAL OBSEQUIO -- stock ficticio: {ficticio} "
              f"(total {sum(ficticio.values())})")
    registrar(f"  {SKU_REAL} Limpia Cristal          -- stock real     : {real} "
              f"(total {sum(real.values())})")
    registrar()

    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    art = c.execute("SELECT id, sku, name, active, notes FROM articles WHERE sku=?",
                    (SKU_FICTICIO,)).fetchone()
    ventas = c.execute(
        "SELECT COUNT(*) FROM sale_items si JOIN articles a"
        " ON a.id=si.article_id OR a.id=si.lens_article_id WHERE a.sku=?",
        (SKU_FICTICIO,)).fetchone()[0] if art else 0
    ya_retirado = c.execute("SELECT COUNT(*) FROM admin_audit_log WHERE action=?",
                            (RETIRO,)).fetchone()[0]
    c.close()

    registrar("== guardas ==")
    comprobar(art is not None, f"{SKU_FICTICIO} existe en el catalogo")
    if art is None:
        return 1
    comprobar(not ya_retirado, f"{SKU_FICTICIO} no fue retirado antes")
    comprobar(bool(art["active"]), f"{SKU_FICTICIO} sigue activo, hay algo que hacer")
    registrar(f"  ---  ventas historicas que lo referencian: {ventas}")
    if ventas:
        registrar("       se conservan: la historia vieja sigue apuntando al articulo viejo")
    if fallas:
        registrar()
        registrar("No se escribe nada.")
        return 1
    registrar()

    if not args.confirmar:
        registrar("NO SE ESCRIBIO NADA: falta --confirmar.")
        registrar(f"Esto haria: compensar {sum(ficticio.values())} unidades ficticias "
                  f"({ficticio}), dejar el stock en cero y desactivar {SKU_FICTICIO}.")
        return 0

    registrar("== backup verificable ==")
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    respaldo = base.parent / "Backups" / f"bc-caja-preretiro-obsequio-{marca}.sqlite3"
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
    ctrl = build_comercial_controller(base)
    try:
        registrar("== 1. compensacion del stock ficticio ==")
        for sucursal, cantidad in sorted(ficticio.items()):
            if cantidad <= 0:
                continue
            ctrl.ledger.registrar(StockMovement(
                article_id=art["id"], destination=Destination(sucursal),
                kind=StockMovementKind.AJUSTE_NEGATIVO, quantity=cantidad, actor=ACTOR,
                occurred_at=cuando, reason_code=MOTIVO,
                note=(f"{CAUSA}. Las {cantidad} unidades de {SKU_FICTICIO} en {sucursal} "
                      f"no eran frascos: eran la ficcion de un articulo creado para poder "
                      f"poner precio cero. No se trasladan a {SKU_REAL} ni a ningun otro. "
                      f"Se llevan a cero antes de retirarlo. V1-013"),
                document_kind="RETIRO_OBSEQUIO_LEGACY",
                document_id=f"retiro-obsequio-{fecha.replace('-', '')}",
                idempotency_key=f"RETIRO_OBSEQUIO:{SKU_FICTICIO}:{sucursal}"))
            registrar(f"  {sucursal}: -{cantidad} unidades")

        registrar()
        registrar("== 2. verificar cero antes de retirar ==")
        quedan = stock_por_sucursal(base, SKU_FICTICIO)
        comprobar(all(v == 0 for v in quedan.values()),
                  f"{SKU_FICTICIO} quedo en cero en todas las sucursales: {quedan}")
        if fallas:
            registrar("NO se retira: todavia hay stock.")
            return 1

        registrar()
        registrar("== 3. retiro del catalogo activo ==")
        ctrl.desactivar_articulo(
            art["id"], actor=ACTOR,
            motivo=(f"{RETIRO}. Mecanismo historico del regalo. Desde V1-013 el obsequio se "
                    f"hace sobre el articulo real {SKU_REAL} con la linea marcada sin costo "
                    f"y descontando stock de verdad. Las ventas anteriores que lo "
                    f"referencien se conservan tal como estan"))
        registrar(f"  {SKU_FICTICIO} desactivado")
    finally:
        ctrl.close()

    conexion = sqlite3.connect(str(base))
    try:
        conexion.execute(
            "INSERT INTO admin_audit_log(id, actor, action, target_type, target_id,"
            " result, details_json, recorded_at) VALUES (?,?,?,?,?,?,?,?)",
            (str(uuid4()), ACTOR, RETIRO, "article", art["id"], "RETIRADO",
             json.dumps(dict(
                 sku=SKU_FICTICIO, nombre=art["name"],
                 stock_ficticio_compensado=ficticio,
                 total_compensado=sum(ficticio.values()),
                 causa=CAUSA,
                 no_se_traslado_a=SKU_REAL,
                 ventas_historicas_que_lo_referencian=ventas,
                 historia="se conserva. No se reemplaza retroactivamente por 000010",
                 desde_ahora=("el obsequio se hace sobre 000010 con no_cost y salida de "
                              "stock real, motivo PROMO_CRISTAL_ARMAZON_LIMPIA"),
                 retirado_el=fecha), ensure_ascii=False, sort_keys=True),
             cuando.isoformat()))
        conexion.commit()
    finally:
        conexion.close()

    registrar()
    registrar("== verificacion ==")
    despues = radiografia(base)
    final = stock_por_sucursal(base, SKU_FICTICIO)
    comprobar(all(v == 0 for v in final.values()), f"{SKU_FICTICIO} en cero: {final}")
    comprobar(stock_por_sucursal(base, SKU_REAL) == real,
              f"{SKU_REAL} intacto: {real}. Las unidades ficticias NO se le trasladaron")
    comprobar(despues["activos"] == antes["activos"] - 1,
              f"activos: {antes['activos']} -> {despues['activos']}")
    comprobar(despues["articulos"] == antes["articulos"],
              f"no se borro ningun articulo: {despues['articulos']}")
    comprobar(despues["movimientos"] == antes["movimientos"] + len([v for v in ficticio.values() if v > 0]),
              f"movimientos: {antes['movimientos']} -> {despues['movimientos']}")
    comprobar(despues["asuncion"] == antes["asuncion"] - ficticio.get("ASUNCION", 0),
              f"stock ASUNCION: {antes['asuncion']} -> {despues['asuncion']}")
    comprobar(despues["pilar"] == antes["pilar"] - ficticio.get("PILAR", 0),
              f"stock PILAR: {antes['pilar']} -> {despues['pilar']}")
    comprobar(despues["stock_en_retirados"] == 0,
              f"stock operativo en articulos retirados: {despues['stock_en_retirados']}")
    for clave, etiqueta in (("integridad", "integrity_check"), ("fk", "foreign_key_check"),
                            ("negativos", "stock negativo"), ("huerfanos", "huerfanos"),
                            ("efectos", "efectos sin hecho")):
        esperado = "ok" if clave == "integridad" else 0
        comprobar(despues[clave] == esperado, f"{etiqueta}: {despues[clave]}")
    for clave in ("entradas", "suma_caja", "sale_items"):
        comprobar(despues[clave] == antes[clave], f"Caja, {clave}: {antes[clave]}")
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    ids = ("inventario-inicial-asuncion-20260803", "inventario-inicial-pilar-20260810")
    comprobar(c.execute("SELECT COUNT(*) FROM stock_movements WHERE document_id IN (?,?)",
                        ids).fetchone()[0] == 3583, "V1-008 intacta: 3.583 movimientos")
    comprobar(c.execute("SELECT COUNT(*) FROM stock_movements WHERE article_id=?",
                        (art["id"],)).fetchone()[0] >= 2,
              "los movimientos originales de 000037 siguen ahi")
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
