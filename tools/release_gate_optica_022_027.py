"""Release / migration gate de las migraciones acumuladas 022 -> 027.

Seis migraciones sin instalar. Este script las trata como lo que son -- un
release productivo -- y no como un tramite: hace backup, corre la cadena sobre
una COPIA de la base real, verifica que no se haya perdido ni cambiado una sola
fila, ejercita el circuito comercial completo incluida la reversion
compensatoria, prueba el rollback y confirma que la base real quedo intacta.

La base real se abre SIEMPRE en modo `ro`. Todo lo que escribe este script
ocurre sobre copias. Si algo falla, el gate falla: no hay pasos opcionales.

    python tools/release_gate_optica_022_027.py [--salida <dir>]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import sqlite3
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from modulos.caja_diaria.config import resolve_data_paths  # noqa: E402
from modulos.caja_diaria.domain.models import (  # noqa: E402
    CashDay,
    CashEntry,
    SaleItem,
)
from modulos.caja_diaria.infrastructure.sqlite_repository import (  # noqa: E402
    SQLiteCashDayRepository,
)
from modulos.comercial.application.stock_ledger import StockLedgerService  # noqa: E402
from modulos.comercial.application.ventas import VentasLedgerIntegrator  # noqa: E402
from modulos.comercial.domain.models import (  # noqa: E402
    Article,
    ArticleNature,
    Destination,
    StockMovement,
    StockMovementKind,
)
from modulos.comercial.infrastructure.sqlite_catalog_repository import (  # noqa: E402
    SQLiteCatalogRepository,
)
from modulos.comercial.infrastructure.sqlite_stock_ledger import (  # noqa: E402
    SQLiteStockLedgerRepository,
)

MIGRACIONES_NUEVAS = ("022", "023", "024", "025", "026", "027")

lineas: list[str] = []
fallas: list[str] = []


def registrar(texto: str = "") -> None:
    print(texto)
    lineas.append(texto)


def comprobar(condicion: bool, descripcion: str) -> bool:
    registrar(f"  {'OK  ' if condicion else 'FALLA'} {descripcion}")
    if not condicion:
        fallas.append(descripcion)
    return bool(condicion)


def sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def copiar_consistente(origen: Path, destino: Path) -> None:
    """Copia por la API de backup de SQLite.

    Copiar el archivo con el sistema de archivos dejaria afuera lo que todavia
    esta en el WAL, que es justo lo ultimo que la Optica escribio.
    """
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


def _huella(conexion: sqlite3.Connection, tabla: str, columnas) -> str:
    """Contenido de una tabla, restringido a un conjunto de columnas.

    Se restringe a proposito: una migracion aditiva agrega columnas, y un
    `SELECT *` daria distinto sin que ninguna fila haya cambiado. Lo que hay que
    comparar es lo que ya existia.
    """
    lista = ", ".join(f'"{c}"' for c in columnas)
    filas = [tuple(str(v) for v in f) for f in conexion.execute(
        f'SELECT {lista} FROM "{tabla}"')]
    return hashlib.sha256(repr(sorted(filas)).encode("utf-8")).hexdigest()


def huellas_previas(ruta: Path, columnas_por_tabla: dict) -> dict:
    """Las mismas huellas, leidas de otra base con las columnas de la primera."""
    conexion = sqlite3.connect(str(ruta))
    try:
        return {tabla: _huella(conexion, tabla, columnas)
                for tabla, columnas in columnas_por_tabla.items()}
    finally:
        conexion.close()


def radiografia(ruta: Path, *, solo_lectura: bool = False) -> dict:
    """Todo lo que hace falta para decir despues si algo se perdio o cambio."""
    uri = f"file:{ruta}?mode=ro" if solo_lectura else str(ruta)
    conexion = sqlite3.connect(uri, uri=solo_lectura)
    conexion.row_factory = sqlite3.Row
    try:
        tablas = sorted(f[0] for f in conexion.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
            " AND name NOT LIKE 'sqlite_%'"))
        vistas = sorted(f[0] for f in conexion.execute(
            "SELECT name FROM sqlite_master WHERE type='view'"))
        disparadores = sorted(f[0] for f in conexion.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"))
        migraciones = sorted(f[0] for f in conexion.execute(
            "SELECT version FROM schema_migrations"))
        conteos = {}
        columnas = {}
        huellas = {}
        for tabla in tablas:
            conteos[tabla] = conexion.execute(
                f'SELECT COUNT(*) FROM "{tabla}"').fetchone()[0]
            columnas[tabla] = [f[1] for f in conexion.execute(
                f'PRAGMA table_info("{tabla}")')]
            huellas[tabla] = _huella(conexion, tabla, columnas[tabla])
        total = conexion.execute(
            "SELECT COALESCE(SUM(total),0) FROM cash_entries").fetchone()[0]
        integridad = conexion.execute("PRAGMA integrity_check").fetchone()[0]
        fk = conexion.execute("PRAGMA foreign_key_check").fetchall()
    finally:
        conexion.close()
    return {"tablas": tablas, "vistas": vistas, "triggers": disparadores,
            "migraciones": migraciones, "conteos": conteos, "huellas": huellas,
            "columnas": columnas,
            "suma_total": total, "integridad": integridad,
            "violaciones_fk": len(fk)}


# --------------------------------------------------------------------------
# El escenario real, sobre la copia ya migrada
# --------------------------------------------------------------------------


def escenario(ruta: Path) -> None:
    catalogo = SQLiteCatalogRepository(ruta)
    ledger_repo = SQLiteStockLedgerRepository(ruta)
    ledger = StockLedgerService(ledger_repo, catalogo)
    integrador = VentasLedgerIntegrator(catalogo, ledger_repo)
    caja = SQLiteCashDayRepository(ruta, sale_integrator=integrador)
    unidad = "GATE-006"
    try:
        caja.bind_register_to_branch(unidad, "ASUNCION", assigned_by="release-gate")

        armazon = catalogo.save_article(Article(
            sku="GATE-ARM", name="Armazón de prueba del gate",
            nature=ArticleNature.PRODUCTO_STOCKEABLE))
        cristal = catalogo.save_article(Article(
            sku="GATE-CRIS", name="Cristal recetado del gate",
            nature=ArticleNature.TRABAJO_BAJO_PEDIDO))
        servicio = catalogo.save_article(Article(
            sku="GATE-SERV", name="Compostura del gate",
            nature=ArticleNature.SERVICIO_NO_STOCKEABLE))
        comprobar(ledger.stock(armazon.id, Destination.ASUNCION) == 0,
                  "catalogo no es stock: el articulo nace en cero")

        ledger.registrar(StockMovement(
            article_id=armazon.id, destination=Destination.ASUNCION,
            kind=StockMovementKind.INGRESO_COMPRA, quantity=3, actor="release-gate",
            idempotency_key="gate:ingreso:armazon"))
        comprobar(ledger.stock(armazon.id, Destination.ASUNCION) == 3,
                  "la entrada de mercaderia sube el stock a 3")

        # Venta legacy: la caja que todavia no vincula articulos se comporta
        # exactamente como hoy. Es la condicion para que instalar no cambie nada.
        dia = CashDay(business_date=date(2026, 8, 18), unit=unidad, opening_cash=0,
                      opened_by="release-gate")
        legacy = CashEntry(description="Armazon/org uvx", saleswoman="ana",
                           total=250_000, cash=250_000,
                           items=(SaleItem(description="Armazon/org uvx",
                                           frame_price=250_000),))
        dia.add_entry(legacy)
        caja.save(dia, edited_by="release-gate")
        comprobar(ledger.movimientos() and all(
            m.document_kind != "VENTA" for m in ledger.movimientos()),
            "una venta sin articulo vinculado no mueve stock")

        # Venta integrada: armazon + cristal en la misma linea.
        venta = CashEntry(
            description="Venta con articulo", saleswoman="ana",
            total=530_000, cash=530_000,
            items=(SaleItem(description="Armazon/org", frame_price=280_000,
                            lens_price=250_000, article_id=armazon.id,
                            lens_article_id=cristal.id),))
        dia.add_entry(venta)
        caja.save(dia, edited_by="release-gate")
        comprobar(ledger.stock(armazon.id, Destination.ASUNCION) == 2,
                  "la venta descuenta una unidad del armazon")
        comprobar(ledger.movimientos(article_id=cristal.id) == [],
                  "el cristal es trabajo bajo pedido: no mueve stock")

        # Venta de puro servicio: hecho durable, cero efectos.
        servicio_entry = CashEntry(
            description="Compostura", saleswoman="ana", total=30_000, cash=30_000,
            items=(SaleItem(description="Compostura", frame_price=30_000,
                            article_id=servicio.id),))
        dia.add_entry(servicio_entry)
        caja.save(dia, edited_by="release-gate")
        comprobar(ledger.stock(armazon.id, Destination.ASUNCION) == 2,
                  "la venta de servicio no toca el stock")

        # ---- reversion compensatoria, el corazon del slice 6 ----
        recargado = caja.get_by_date_and_unit(dia.business_date, unidad)
        integrada = next(e for e in recargado.entries
                         if e.description == "Venta con articulo")
        recargado.void_entry(integrada.id, "Gate: venta cargada por error")
        caja.save(recargado, audit_reason="gate", edited_by="release-gate")

        comprobar(ledger.stock(armazon.id, Destination.ASUNCION) == 3,
                  "anular la venta devuelve exactamente la unidad que saco")

        conexion = sqlite3.connect(str(ruta))
        conexion.row_factory = sqlite3.Row
        try:
            comprobar(conexion.execute(
                "SELECT COUNT(*) FROM domain_events WHERE event_type='SALE_COMPLETED'"
            ).fetchone()[0] == 2,
                "los SALE_COMPLETED originales siguen estando")
            comprobar(conexion.execute(
                "SELECT COUNT(*) FROM domain_events WHERE event_type='SALE_VOIDED'"
            ).fetchone()[0] == 1,
                "la anulacion quedo como hecho durable")
            comprobar(conexion.execute(
                "SELECT COUNT(*) FROM stock_movements WHERE kind='VENTA'"
            ).fetchone()[0] == 1,
                "el movimiento VENTA original no se borro")
            fila = conexion.execute(
                "SELECT * FROM stock_origen_anulacion").fetchone()
            comprobar(fila is not None and fila["voided_by"] == "release-gate"
                      and fila["void_reason"] == "Gate: venta cargada por error",
                      "de la unidad devuelta se llega a la venta y a quien la anulo")
            comprobar(conexion.execute(
                "SELECT status FROM cash_entries WHERE id = ?",
                (integrada.id,)).fetchone()[0] == "VOIDED",
                "la venta anulada sigue en el dia, marcada")
        finally:
            conexion.close()

        # Idempotencia sobre la copia real: reguardar no duplica nada.
        otra_vez = caja.get_by_date_and_unit(dia.business_date, unidad)
        caja.save(otra_vez, edited_by="release-gate")
        comprobar(ledger.stock(armazon.id, Destination.ASUNCION) == 3,
                  "reguardar el dia no devuelve el stock dos veces")

        final = caja.get_by_date_and_unit(dia.business_date, unidad)
        comprobar(final.totals().total == 280_000,
                  "Caja descuenta la venta anulada del total y no la cuenta dos veces")
    finally:
        for recurso in (caja, ledger_repo, catalogo):
            cerrar = getattr(recurso, "close", None)
            if cerrar is not None:
                cerrar()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--salida", default=None)
    parser.add_argument("--base", default=None,
                        help="base a usar como origen; por defecto la instalada")
    args = parser.parse_args()

    real = (Path(args.base) if args.base
            else resolve_data_paths().database)
    if not real.exists():
        registrar(f"no hay base en {real}")
        return 2

    trabajo = Path(args.salida) if args.salida else Path(
        os.environ.get("TEMP", ".")) / "bc-release-gate-006"
    trabajo.mkdir(parents=True, exist_ok=True)
    backup = trabajo / "bc_caja.BACKUP.sqlite3"
    copia = trabajo / "bc_caja.COPIA.sqlite3"

    sha_antes = sha256(real)
    registrar(f"base de origen  : {real}")
    registrar(f"sha256 antes    : {sha_antes}")

    antes = radiografia(real, solo_lectura=True)
    registrar(f"tablas antes    : {len(antes['tablas'])}")
    registrar(f"migraciones antes: {len(antes['migraciones'])} -> "
              f"{max(antes['migraciones'])}")
    registrar(f"cash_entries    : {antes['conteos'].get('cash_entries')}")
    registrar(f"sale_items      : {antes['conteos'].get('sale_items')}")
    registrar(f"SUM(total)      : {antes['suma_total']}")
    registrar()

    registrar("== backup ==")
    copiar_consistente(real, backup)
    comprobar(backup.exists() and backup.stat().st_size > 0,
              f"backup consistente en {backup.name}")
    respaldo = radiografia(backup)
    comprobar(respaldo["conteos"] == antes["conteos"],
              "el backup tiene las mismas filas que la base de origen")
    comprobar(respaldo["huellas"] == antes["huellas"],
              "el backup tiene el mismo contenido, fila por fila")
    sha_backup = sha256(backup)
    registrar()

    registrar("== upgrade secuencial 021 -> 027 sobre la copia ==")
    copiar_consistente(real, copia)
    SQLiteCashDayRepository(copia).close()
    despues = radiografia(copia)

    comprobar(set(antes["tablas"]) <= set(despues["tablas"]),
              "ninguna tabla se perdio")
    nuevas = [m for m in MIGRACIONES_NUEVAS if m in despues["migraciones"]]
    comprobar(nuevas == list(MIGRACIONES_NUEVAS),
              f"la cadena aplico {' '.join(MIGRACIONES_NUEVAS)}")
    comprobar(len(despues["migraciones"]) == len(antes["migraciones"]) + 6,
              f"{len(antes['migraciones'])} -> {len(despues['migraciones'])} migraciones")
    comprobar(despues["integridad"] == "ok", "integrity_check ok")
    comprobar(despues["violaciones_fk"] == 0, "foreign_key_check sin violaciones")

    # Comparadas sobre las columnas que ya existian: la 022 y la 025 le agregan
    # columnas a sale_items, y eso no es un cambio de datos.
    posteriores = huellas_previas(copia, antes["columnas"])
    cambiadas = [t for t in antes["tablas"]
                 if t != "schema_migrations"
                 and antes["huellas"][t] != posteriores.get(t)]
    comprobar(not cambiadas,
              f"ninguna fila existente cambio (revisadas {len(antes['tablas'])} tablas)")
    if cambiadas:
        registrar(f"       tablas cambiadas: {cambiadas}")
    comprobar(despues["conteos"].get("cash_entries") == antes["conteos"].get("cash_entries"),
              "cash_entries preservadas")
    comprobar(despues["conteos"].get("sale_items") == antes["conteos"].get("sale_items"),
              "sale_items preservadas")
    comprobar(despues["suma_total"] == antes["suma_total"],
              f"SUM(cash_entries.total) sin cambios: {despues['suma_total']}")

    for objeto in ("articles", "stock_movements", "domain_events", "event_effects",
                   "suppliers", "purchases", "purchase_lines",
                   "purchase_line_distributions", "sale_stock_integrations",
                   "sale_void_compensations"):
        comprobar(objeto in despues["tablas"], f"tabla nueva presente: {objeto}")
    for vista in ("stock_actual", "stock_origen_compra", "stock_origen_venta",
                  "stock_origen_anulacion"):
        comprobar(vista in despues["vistas"], f"vista nueva presente: {vista}")
    for trigger in ("cash_entries_integrada_sin_anular",
                    "cash_entries_anulada_no_revive",
                    "sale_void_compensations_sin_reversion_parcial",
                    "sale_void_compensations_cuenta_declarada_real",
                    "stock_movements_venta_anulada_solo_compensa"):
        comprobar(trigger in despues["triggers"], f"trigger nuevo presente: {trigger}")
    registrar()

    registrar("== escenario real de punta a punta, sobre la copia migrada ==")
    escenario(copia)
    registrar()

    registrar("== rollback ==")
    copia.unlink(missing_ok=True)
    shutil.copy2(backup, copia)
    revertida = radiografia(copia)
    comprobar(sha256(copia) == sha_backup,
              "la base restaurada es byte a byte el backup")
    comprobar(max(revertida["migraciones"]) == max(antes["migraciones"]),
              f"la cadena vuelve a {max(antes['migraciones'])}")
    comprobar(not [m for m in MIGRACIONES_NUEVAS if m in revertida["migraciones"]],
              "ninguna de las seis migraciones nuevas quedo aplicada")
    comprobar(huellas_previas(copia, antes["columnas"]) == antes["huellas"],
              "los datos vuelven exactamente a como estaban")
    registrar()

    sha_despues = sha256(real)
    registrar(f"sha256 despues  : {sha_despues}")
    comprobar(sha_despues == sha_antes, "la base de origen quedo intacta")
    registrar()

    veredicto = "PASS" if not fallas else "FALLA"
    registrar(f"VEREDICTO: {veredicto} ({len(fallas)} fallas)")
    for falla in fallas:
        registrar(f"  - {falla}")

    destino = RAIZ / "artifacts" / "BC-OPTICA-VENTA-REVERSIBLE-Y-RELEASE-GATE-V1-006"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "RELEASE_GATE_022_027.txt").write_text(
        "\n".join(lineas) + "\n", encoding="utf-8")
    return 0 if not fallas else 1


if __name__ == "__main__":
    raise SystemExit(main())
