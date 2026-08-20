# -*- coding: utf-8 -*-
"""Aplica la migración 030 —usuarios y roles— sobre la base de la Óptica.

Aditiva: agrega cuatro columnas descriptivas a `admin_users` y le pone nombre al
administrador que ya existe. No crea tablas, no borra nada y no toca una sola
fila de operación. La columna `role` ya existía con `DEFAULT 'ADMIN'`, así que
quien hoy entra al panel sigue siendo administradora sin que nadie la actualice.

    python tools/usuarios_migracion_030_optica.py [--base <ruta>] [--confirmar]

Sin `--confirmar` no escribe: dice qué haría y sale.
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
from modulos.caja_diaria.infrastructure.sqlite_repository import (  # noqa: E402
    SQLiteCashDayRepository,
)

VERSION = "030"
COLUMNAS_NUEVAS = ("display_name", "branch", "created_by", "updated_by")

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
    """Todo lo que la 030 promete no mover."""
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        q = lambda s, *a: c.execute(s, a).fetchone()[0]  # noqa: E731
        return dict(
            migraciones=q("SELECT COUNT(*) FROM schema_migrations"),
            usuarios=q("SELECT COUNT(*) FROM admin_users"),
            usuarios_activos=q("SELECT COUNT(*) FROM admin_users WHERE active=1"),
            dias=q("SELECT COUNT(*) FROM cash_days"),
            entradas=q("SELECT COUNT(*) FROM cash_entries"),
            suma_caja=q("SELECT COALESCE(SUM(total),0) FROM cash_entries WHERE status='ACTIVE'"),
            sale_items=q("SELECT COUNT(*) FROM sale_items"),
            articulos=q("SELECT COUNT(*) FROM articles"),
            movimientos=q("SELECT COUNT(*) FROM stock_movements"),
            trabajos=q("SELECT COUNT(*) FROM tracked_works"),
            laboratorios=q("SELECT COUNT(*) FROM laboratories"),
            factufacil=q("SELECT COUNT(*) FROM factufacil_loads"),
            pedidos=q("SELECT COUNT(*) FROM orders"),
            integridad=q("PRAGMA integrity_check"),
            fk=len(c.execute("PRAGMA foreign_key_check").fetchall()),
        )
    finally:
        c.close()


def columnas(base: Path, tabla: str) -> set[str]:
    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    try:
        return {f[1] for f in c.execute(f"PRAGMA table_info({tabla})")}
    finally:
        c.close()


def versiones(base: Path) -> set[str]:
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
    registrar("MIGRACION 030 -- usuarios y roles en BC Caja")
    registrar(f"base   : {base}")
    if not base.exists():
        registrar("La base no existe. No se escribe nada.")
        return 1
    registrar(f"sha256 : {sha256(base)}")
    registrar()

    antes = radiografia(base)
    columnas_antes = columnas(base, "admin_users")
    registrar("== estado antes ==")
    for clave, valor in antes.items():
        registrar(f"  {clave:18s} {valor}")
    registrar()

    registrar("== pre-guards ==")
    comprobar(antes["integridad"] == "ok", "integrity_check ok antes de tocar nada")
    comprobar(antes["fk"] == 0, "sin FK rotas antes")
    if VERSION in versiones(base):
        registrar()
        registrar("La 030 ya esta aplicada. No hay nada que hacer.")
        comprobar(set(COLUMNAS_NUEVAS) <= columnas_antes,
                  "las cuatro columnas estan")
        registrar("Idempotencia: correr esto de nuevo no cambia nada.")
        _volcar(args.salida)
        return 1 if fallas else 0
    ya = [c for c in COLUMNAS_NUEVAS if c in columnas_antes]
    comprobar(not ya, f"las columnas nuevas todavia no existen ({ya})")
    comprobar("029" in versiones(base),
              "la 029 esta aplicada: esta base viene de la linea correcta")
    if fallas:
        registrar()
        registrar("Alguna guarda fallo. No se escribe nada.")
        _volcar(args.salida)
        return 1
    registrar()

    if not args.confirmar:
        registrar("DRY-RUN: no se escribio nada. Falta --confirmar.")
        registrar(f"Esto aplicaria la migracion {VERSION}, que agrega a admin_users:")
        for columna in COLUMNAS_NUEVAS:
            registrar(f"  - {columna}")
        registrar(f"Y le pondria display_name a los {antes['usuarios']} usuario(s) que"
                  " ya existen, con su propio username.")
        registrar("Ninguna otra tabla se toca y ningun dato de operacion cambia.")
        _volcar(args.salida)
        return 0

    registrar("== backup verificable ==")
    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    respaldo = base.parent / "Backups" / f"bc-caja-preusuarios-{sello}.sqlite3"
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
    repositorio = SQLiteCashDayRepository(base)
    try:
        repositorio.integrity_check()
    finally:
        repositorio.close()
    registrar(f"  aplicada la {VERSION}")
    registrar()

    registrar("== post-checks ==")
    despues = radiografia(base)
    comprobar(VERSION in versiones(base), f"schema_migrations registra la {VERSION}")
    comprobar(despues["migraciones"] == antes["migraciones"] + 1,
              f"migraciones: {antes['migraciones']} -> {despues['migraciones']}")
    columnas_despues = columnas(base, "admin_users")
    comprobar(columnas_despues - columnas_antes == set(COLUMNAS_NUEVAS),
              f"exactamente cuatro columnas nuevas ({columnas_despues - columnas_antes})")
    for clave in ("usuarios", "usuarios_activos", "dias", "entradas", "suma_caja",
                  "sale_items", "articulos", "movimientos", "trabajos",
                  "laboratorios", "factufacil", "pedidos"):
        comprobar(antes[clave] == despues[clave],
                  f"{clave}: {antes[clave]} sin cambio")
    comprobar(despues["integridad"] == "ok", "integrity_check ok")
    comprobar(despues["fk"] == 0, "FK 0")

    c = sqlite3.connect(f"file:{base}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        filas = c.execute("SELECT username, display_name, role, active FROM admin_users").fetchall()
    finally:
        c.close()
    for fila in filas:
        registrar(f"  usuario: {fila['username']} · {fila['display_name']}"
                  f" · {fila['role']} · {'activa' if fila['active'] else 'inactiva'}")
    comprobar(all(f["display_name"] for f in filas),
              "todos los usuarios que ya existian tienen nombre")
    comprobar(all(f["role"] == "ADMIN" for f in filas),
              "y siguen siendo ADMIN: nadie perdio acceso al panel")

    repositorio = SQLiteCashDayRepository(base)
    repositorio.close()
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
