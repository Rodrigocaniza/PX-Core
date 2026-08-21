"""Smoke del ejecutable empaquetado, sobre una COPIA de la base real.

Empaquetar y que compile no dice nada sobre si el ejecutable arranca ni sobre si
la cadena 022-027 se aplica desde adentro del paquete. Eso es lo que este script
verifica, y lo hace contra una copia: el ejecutable nunca ve la base real.

    python tools/smoke_release_006.py [--paquete dist/BC-Caja] [--base <ruta>]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from modulos.caja_diaria.config import resolve_data_paths  # noqa: E402

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


def copiar_consistente(origen: Path, destino: Path) -> None:
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


def estado(ruta: Path) -> dict:
    conexion = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    try:
        return {
            "migraciones": sorted(f[0] for f in conexion.execute(
                "SELECT version FROM schema_migrations")),
            "cash_entries": conexion.execute(
                "SELECT COUNT(*) FROM cash_entries").fetchone()[0],
            "sale_items": conexion.execute(
                "SELECT COUNT(*) FROM sale_items").fetchone()[0],
            "suma": conexion.execute(
                "SELECT COALESCE(SUM(total),0) FROM cash_entries").fetchone()[0],
            "integridad": conexion.execute(
                "PRAGMA integrity_check").fetchone()[0],
        }
    finally:
        conexion.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paquete", default=str(RAIZ / "dist" / "BC-Caja"))
    parser.add_argument("--base", default=None)
    parser.add_argument("--espera", type=int, default=30)
    parser.add_argument("--datos", default=None)
    args = parser.parse_args()

    paquete = Path(args.paquete)
    ejecutable = paquete / "BC-Caja.exe"
    real = Path(args.base) if args.base else resolve_data_paths().database

    registrar(f"paquete       : {paquete}")
    registrar(f"base de origen: {real}")

    comprobar(ejecutable.exists(), "el ejecutable existe")
    version = (paquete / "VERSION.txt")
    comprobar(version.exists(), "el paquete lleva su VERSION.txt")
    if version.exists():
        etiqueta = version.read_text(encoding="utf-8").splitlines()[0]
        registrar(f"version       : {etiqueta}")
    migraciones_empaquetadas = sorted(
        p.name for p in (paquete / "_internal" / "modulos" / "caja_diaria"
                         / "infrastructure" / "migrations").glob("*.sql"))
    comprobar(len(migraciones_empaquetadas) == 27,
              f"las 27 migraciones viajan dentro del paquete "
              f"({len(migraciones_empaquetadas)} encontradas)")
    comprobar("027_sale_void_compensation.sql" in migraciones_empaquetadas,
              "la 027 esta empaquetada")
    if not ejecutable.exists():
        return 2

    datos = Path(args.datos) if args.datos else (
        Path(os.environ.get("TEMP", ".")) / "bc-smoke-006")
    datos.mkdir(parents=True, exist_ok=True)
    base = datos / "bc_caja.sqlite3"
    copiar_consistente(real, base)
    sha_real_antes = hashlib.sha256(real.read_bytes()).hexdigest()
    antes = estado(base)
    registrar(f"copia         : {base}")
    registrar(f"antes         : {len(antes['migraciones'])} migraciones, "
              f"{antes['cash_entries']} entradas, suma {antes['suma']}")
    registrar()

    registrar("== arranque del ejecutable ==")
    entorno = dict(os.environ, BC_CAJA_DATA_DIR=str(datos))
    proceso = subprocess.Popen([str(ejecutable)], env=entorno, cwd=str(paquete))
    try:
        limite = time.time() + args.espera
        migrada = False
        while time.time() < limite:
            time.sleep(2)
            if proceso.poll() is not None:
                break
            try:
                if "027" in estado(base)["migraciones"]:
                    migrada = True
                    break
            except sqlite3.Error:
                continue
        vivo = proceso.poll() is None
        comprobar(vivo, "el ejecutable sigue vivo y no se cayo al arrancar")
        comprobar(migrada, "el ejecutable aplico la cadena hasta la 027 por su cuenta")
    finally:
        if proceso.poll() is None:
            proceso.terminate()
            try:
                proceso.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proceso.kill()
                proceso.wait(timeout=20)
    registrar()

    registrar("== despues del arranque ==")
    despues = estado(base)
    registrar(f"despues       : {len(despues['migraciones'])} migraciones, "
              f"{despues['cash_entries']} entradas, suma {despues['suma']}")
    comprobar(despues["integridad"] == "ok", "integrity_check ok tras el arranque")
    comprobar(despues["cash_entries"] == antes["cash_entries"],
              "las entradas de Caja siguen ahi")
    comprobar(despues["sale_items"] == antes["sale_items"],
              "las lineas de venta siguen ahi")
    comprobar(despues["suma"] == antes["suma"],
              "el dinero registrado no cambio")

    registro = datos / "Logs" / "sqlite-errors.log"
    comprobar(not registro.exists() or not registro.read_text(
        encoding="utf-8", errors="replace").strip(),
        "sin errores de SQLite en el log")

    comprobar(hashlib.sha256(real.read_bytes()).hexdigest() == sha_real_antes,
              "la base de origen quedo intacta")
    registrar()

    veredicto = "PASS" if not fallas else "FALLA"
    registrar(f"VEREDICTO: {veredicto} ({len(fallas)} fallas)")
    for falla in fallas:
        registrar(f"  - {falla}")

    destino = RAIZ / "artifacts" / "BC-OPTICA-VENTA-REVERSIBLE-Y-RELEASE-GATE-V1-006"
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "PACKAGING_Y_SMOKE.txt").write_text(
        "\n".join(lineas) + "\n", encoding="utf-8")
    return 0 if not fallas else 1


if __name__ == "__main__":
    raise SystemExit(main())
