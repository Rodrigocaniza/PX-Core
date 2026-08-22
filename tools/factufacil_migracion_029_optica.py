# -*- coding: utf-8 -*-
"""Aplica la migración 029 —FactuFácil en Caja— sobre la base de la Óptica.

La 029 es aditiva: crea dos tablas que no existían y no toca ninguna. No hay
datos que convertir, no hay columnas que cambiar de tipo, y una versión anterior
de BC Caja abre la base migrada sin enterarse. Aun así se aplica con backup y
post-checks, porque «no debería pasar nada» no es lo mismo que comprobarlo.

    python tools/factufacil_migracion_029_optica.py [--base <ruta>] [--confirmar]

Sin `--confirmar` no escribe: dice qué haría y sale. Ese es el dry-run.
"""

from __future__ import annotations

import argparse
import hashlib
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from modulos.caja_diaria.config import resolve_data_paths  # noqa: E402
from tools.aplicar_migracion_optica import aplicar_una  # noqa: E402

VERSION = "029"
TABLAS_NUEVAS = ("factufacil_loads", "factufacil_history")

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
    """Todo lo que la 029 promete no mover."""
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        q = lambda s, *a: c.execute(s, a).fetchone()[0]  # noqa: E731
        return dict(
            migraciones=q("SELECT COUNT(*) FROM schema_migrations"),
            dias=q("SELECT COUNT(*) FROM cash_days"),
            entradas=q("SELECT COUNT(*) FROM cash_entries"),
            entradas_activas=q("SELECT COUNT(*) FROM cash_entries WHERE status='ACTIVE'"),
            suma_caja=q("SELECT COALESCE(SUM(total),0) FROM cash_entries WHERE status='ACTIVE'"),
            sale_items=q("SELECT COUNT(*) FROM sale_items"),
            articulos=q("SELECT COUNT(*) FROM articles"),
            movimientos=q("SELECT COUNT(*) FROM stock_movements"),
            asuncion=q("SELECT COALESCE(SUM(quantity),0) FROM stock_movements"
                       " WHERE destination='ASUNCION'"),
            pilar=q("SELECT COALESCE(SUM(quantity),0) FROM stock_movements"
                    " WHERE destination='PILAR'"),
            integridad=q("PRAGMA integrity_check"),
            fk=len(c.execute("PRAGMA foreign_key_check").fetchall()),
            negativos=q("SELECT COUNT(*) FROM stock_actual WHERE quantity<0"),
        )
    finally:
        c.close()


def tablas(base: Path) -> set[str]:
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        return {f[0] for f in c.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        c.close()


def ya_aplicada(base: Path) -> bool:
    return VERSION in _versiones(base)


def _versiones(base: Path) -> set[str]:
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        return {f[0] for f in c.execute("SELECT version FROM schema_migrations")}
    finally:
        c.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=None)
    parser.add_argument("--confirmar", action="store_true")
    parser.add_argument("--salida", default=None)
    args = parser.parse_args()

    base = Path(args.base) if args.base else Path(resolve_data_paths().database)
    registrar("MIGRACION 029 -- FactuFacil dentro de BC Caja")
    registrar(f"base   : {base}")
    if not base.exists():
        registrar("La base no existe. No se escribe nada.")
        return 1
    registrar(f"sha256 : {sha256(base)}")
    registrar()

    antes = radiografia(base)
    tablas_antes = tablas(base)
    registrar("== estado antes ==")
    for clave, valor in antes.items():
        registrar(f"  {clave:18s} {valor}")
    registrar()

    registrar("== pre-guards ==")
    comprobar(antes["integridad"] == "ok", "integrity_check ok antes de tocar nada")
    comprobar(antes["fk"] == 0, "sin FK rotas antes")
    faltantes = [t for t in TABLAS_NUEVAS if t in tablas_antes]
    if ya_aplicada(base):
        registrar()
        registrar("La 029 ya esta aplicada. No hay nada que hacer.")
        comprobar(all(t in tablas_antes for t in TABLAS_NUEVAS),
                  "las dos tablas de FactuFacil existen")
        registrar("Idempotencia: correr esto de nuevo no cambia nada.")
        _volcar(args.salida)
        return 1 if fallas else 0
    comprobar(not faltantes,
              f"las tablas de FactuFacil todavia no existen ({faltantes})")
    comprobar("028" in _versiones(base),
              "la 028 esta aplicada: esta base viene de la linea correcta")
    if fallas:
        registrar()
        registrar("Alguna guarda fallo. No se escribe nada.")
        _volcar(args.salida)
        return 1
    registrar()

    if not args.confirmar:
        registrar("DRY-RUN: no se escribio nada. Falta --confirmar.")
        registrar(f"Esto aplicaria la migracion {VERSION} y crearia dos tablas nuevas:")
        for tabla in TABLAS_NUEVAS:
            registrar(f"  - {tabla}")
        registrar("Ninguna tabla existente se modifica, y ningun dato se convierte.")
        _volcar(args.salida)
        return 0

    registrar("== backup verificable ==")
    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    respaldo = base.parent / "Backups" / f"bc-caja-prefactufacil-{sello}.sqlite3"
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
    comprobar(radiografia(respaldo) == antes,
              "el backup tiene el mismo contenido que la base")
    if fallas:
        registrar("El backup no quedo bien. No se escribe nada.")
        _volcar(args.salida)
        return 1
    registrar()

    registrar("== migracion ==")
    # Se ejecuta exactamente la 029 y nada mas. Antes esto construia el
    # repositorio, que aplica todas las migraciones pendientes: escrito cuando
    # la 029 era la punta de la cola, corrido mas tarde llevaba la base hasta
    # el final sin decirlo. Es el F2 de BC-OPTICA-DESPLIEGUE-PRODUCTIVO-029-032.
    try:
        archivo = aplicar_una(base, VERSION)
    except Exception as exc:  # noqa: BLE001
        registrar(f"  FALLO: {exc}")
        registrar(f"  Rollback: copiar {respaldo.name} sobre {base.name}")
        _volcar(args.salida)
        return 1
    registrar(f"  ejecutado {archivo.name}")
    registrar(f"  aplicada la {VERSION}")
    registrar()

    registrar("== post-checks ==")
    despues = radiografia(base)
    tablas_despues = tablas(base)
    comprobar(ya_aplicada(base), f"schema_migrations registra la {VERSION}")
    comprobar(despues["migraciones"] == antes["migraciones"] + 1,
              f"migraciones: {antes['migraciones']} -> {despues['migraciones']}")
    for tabla in TABLAS_NUEVAS:
        comprobar(tabla in tablas_despues, f"existe {tabla}")
    comprobar(tablas_despues - tablas_antes == set(TABLAS_NUEVAS),
              f"no aparecio ninguna otra tabla ({tablas_despues - tablas_antes})")
    for clave in ("dias", "entradas", "entradas_activas", "suma_caja", "sale_items",
                  "articulos", "movimientos", "asuncion", "pilar"):
        comprobar(antes[clave] == despues[clave],
                  f"{clave}: {antes[clave]} sin cambio")
    comprobar(despues["integridad"] == "ok", "integrity_check ok")
    comprobar(despues["fk"] == 0, "FK 0")
    comprobar(despues["negativos"] == 0, "negativos 0")

    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        vacias = all(c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0
                     for t in TABLAS_NUEVAS)
    finally:
        c.close()
    comprobar(vacias, "las tablas nuevas nacen vacias: no se invento ninguna marca")

    # Volver a correr la herramienta no reaplica nada ni sigue con la cola.
    # Este mismo chequeo fue el que denuncio el F2: construir el repositorio
    # aca aplicaba las migraciones siguientes y la radiografia dejaba de dar.
    try:
        aplicar_una(base, VERSION)
        repetible = False
    except RuntimeError:
        repetible = True
    except Exception as exc:  # noqa: BLE001
        # La migracion ya esta escrita: que este chequeo reviente no puede
        # llevarse la evidencia con el. Una base bloqueada porque alguien dejo
        # BC Caja abierta entra por aca.
        registrar(f"  no se pudo comprobar la idempotencia: {exc}")
        repetible = False
    comprobar(repetible, "volver a correrlo no reaplica la migracion")
    comprobar(radiografia(base) == despues,
              "idempotencia: volver a migrar no cambia nada")
    registrar()
    registrar(f"rollback si hiciera falta: copiar {respaldo.name} sobre {base.name}")
    _volcar(args.salida)
    return 1 if fallas else 0


def _volcar(salida: str | None) -> None:
    if salida:
        Path(salida).write_text("\n".join(lineas) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
