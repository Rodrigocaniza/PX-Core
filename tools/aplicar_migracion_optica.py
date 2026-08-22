# -*- coding: utf-8 -*-
"""Aplica UNA migracion sobre la base de la Optica, de a una y con evidencia.

Existen `factufacil_migracion_029_optica.py` y `usuarios_migracion_030_optica.py`
con post-checks propios de su slice. Esta herramienta es la generica para el
resto de la cola: aplica exactamente la version pedida -ni la anterior ni la
siguiente-, exige que la cadena previa este completa, y compara una radiografia
de antes contra una de despues para que «no toco nada» sea una comprobacion y
no una promesa.

    python tools/aplicar_migracion_optica.py 031 [--base <ruta>] [--confirmar]

Sin `--confirmar` no escribe: dice que haria y sale. Ese es el dry-run.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from modulos.caja_diaria.config import resolve_data_paths  # noqa: E402
from tools.radiografia_productiva_optica import comparar, radiografia  # noqa: E402

MIGRACIONES = RAIZ / "modulos" / "caja_diaria" / "infrastructure" / "migrations"

# Lo que cada version tiene que haber dejado en la base. No alcanza con que el
# script no reviente: si la tabla no esta, la migracion no paso.
ESPERADO: dict[str, dict] = {
    "029": {
        "tablas": ("factufacil_loads", "factufacil_history"),
        "columnas": {},
        "sin_tablas": (),
    },
    "030": {
        "tablas": (),
        "columnas": {"admin_users": ("display_name", "branch", "created_by", "updated_by")},
        "sin_tablas": (),
    },
    "031": {
        "tablas": ("service_job_types", "service_jobs", "service_job_events",
                   "service_commission_policy", "service_job_commissions"),
        "columnas": {},
        "sin_tablas": (),
    },
    "032": {
        "tablas": ("service_commission_policy_versions",),
        "columnas": {"service_job_commissions": ("policy_id",)},
        # La 032 no es aditiva: reemplaza la tabla de politica de la 031 por el
        # log de versiones. Que `service_commission_policy` siga existiendo
        # significa que la migracion quedo a medias.
        "sin_tablas": ("service_commission_policy",),
    },
}

lineas: list[str] = []
fallas: list[str] = []


def registrar(texto: str = "") -> None:
    print(texto, flush=True)
    lineas.append(texto)


def comprobar(condicion: bool, descripcion: str) -> bool:
    registrar(f"  {'OK   ' if condicion else 'FALLA'} {descripcion}")
    if not condicion:
        fallas.append(descripcion)
    return bool(condicion)


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def aplicadas(base: Path) -> list[str]:
    con = sqlite3.connect(f"file:{base.as_posix()}?mode=ro", uri=True)
    try:
        return [r[0] for r in con.execute(
            "SELECT version FROM schema_migrations ORDER BY version")]
    finally:
        con.close()


def tablas_de(base: Path) -> set[str]:
    con = sqlite3.connect(f"file:{base.as_posix()}?mode=ro", uri=True)
    try:
        return {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()


def columnas_de(base: Path, tabla: str) -> set[str]:
    con = sqlite3.connect(f"file:{base.as_posix()}?mode=ro", uri=True)
    try:
        return {r[1] for r in con.execute(f"PRAGMA table_info({tabla})")}
    finally:
        con.close()


def version_de(archivo: Path) -> str:
    return archivo.stem.split("_", 1)[0]


def aplicar_una(base: Path, version: str) -> Path:
    """Ejecuta exactamente `version`, ni la anterior ni la siguiente.

    Es una funcion aparte y no codigo dentro de `main` porque las herramientas
    de la 029 y la 030 la necesitan igual. Esas dos se escribieron cuando su
    migracion era la punta de la cola y aplicaban la migracion construyendo
    `SQLiteCashDayRepository`, que corre todas las pendientes. Corridas mas
    tarde llevaban la base hasta el final de la cola sin decirlo: ese es el F2.

    Levanta `RuntimeError` si la version ya esta aplicada, si falta alguna
    previa, o si no hay exactamente un archivo para esa version. Aplicar fuera
    de orden no esta contemplado y no se hace en silencio.
    """
    ya = aplicadas(base)
    if version in ya:
        raise RuntimeError(f"la {version} ya esta aplicada")
    faltantes = sorted({version_de(p) for p in MIGRACIONES.glob("*.sql")
                        if version_de(p) < version and version_de(p) not in ya})
    if faltantes:
        raise RuntimeError(f"faltan migraciones previas: {faltantes}")
    candidatas = sorted(MIGRACIONES.glob(f"{version}_*.sql"))
    if len(candidatas) != 1:
        raise RuntimeError(f"no hay exactamente un archivo {version}_*.sql: {candidatas}")
    archivo = candidatas[0]
    con = sqlite3.connect(str(base))
    try:
        con.executescript(archivo.read_text(encoding="utf-8"))
        con.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, datetime.now().astimezone().isoformat()))
        con.commit()
    finally:
        con.close()
    return archivo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="version a aplicar, por ejemplo 031")
    parser.add_argument("--base", type=Path, default=None)
    parser.add_argument("--confirmar", action="store_true")
    parser.add_argument("--sin-backup", action="store_true",
                        help="para dry-runs sobre una copia: no duplica el archivo")
    args = parser.parse_args()

    version = args.version.zfill(3)
    base = args.base or resolve_data_paths().database
    sello = datetime.now().strftime("%Y%m%d-%H%M%S")

    registrar(f"MIGRACION {version} SOBRE LA BASE DE LA OPTICA")
    registrar("=" * 60)
    registrar(f"base    {base}")
    registrar(f"modo    {'APLICAR' if args.confirmar else 'DRY-RUN (no escribe)'}")
    registrar()

    if not base.exists():
        registrar(f"No existe la base: {base}")
        return 2

    candidatas = sorted(MIGRACIONES.glob(f"{version}_*.sql"))
    if len(candidatas) != 1:
        registrar(f"No hay exactamente un archivo {version}_*.sql: {candidatas}")
        return 2
    archivo = candidatas[0]

    registrar("Estado previo")
    ya = aplicadas(base)
    registrar(f"  aplicadas   {len(ya)} (ultima {ya[-1] if ya else 'ninguna'})")
    registrar(f"  archivo     {archivo.name}")
    registrar(f"  sha256 base {sha256(base)}")
    registrar()

    if version in ya:
        registrar(f"La {version} ya esta aplicada. No hay nada que hacer.")
        return 0

    # La cadena se aplica en orden: 032 detras de 031, 031 detras de 030.
    faltantes = [v for v in sorted(ESPERADO) if v < version and v not in ya]
    previas_del_repo = sorted(
        p.stem.split("_", 1)[0] for p in MIGRACIONES.glob("*.sql"))
    faltantes += [v for v in previas_del_repo if v < version and v not in ya
                  and v not in faltantes]
    if faltantes:
        registrar(f"STOP: faltan migraciones previas: {sorted(faltantes)}")
        registrar("Aplicarlas fuera de orden no esta contemplado.")
        return 1

    antes = radiografia(base)
    registrar("Invariantes productivos antes")
    registrar(f"  integridad   {antes['integridad']}")
    registrar(f"  fk_check     {antes['foreign_key_check'] or 'sin violaciones'}")
    registrar(f"  cash_entries {antes['caja']['entradas']} por {antes['caja']['total']}")
    registrar(f"  articulos    {antes['catalogo']['articulos']}")
    registrar(f"  movimientos  {antes['stock']['movimientos']}")
    registrar(f"  pedidos      {antes['pedidos']['cantidad']}")
    registrar()

    esperado = ESPERADO.get(version, {"tablas": (), "columnas": {}, "sin_tablas": ()})
    if not args.confirmar:
        registrar("Lo que haria")
        registrar(f"  backup      {base.parent / 'Backups'}/bc-caja-pre-{version}-{sello}.sqlite3")
        registrar(f"  ejecutar    {archivo.name}")
        for t in esperado["tablas"]:
            registrar(f"  crear       {t}")
        for t, cols in esperado["columnas"].items():
            registrar(f"  columnas    {t}: {', '.join(cols)}")
        for t in esperado["sin_tablas"]:
            registrar(f"  reemplazar  {t} (deja de existir)")
        registrar()
        registrar("DRY-RUN: no se escribio nada. Repetir con --confirmar.")
        return 0

    copia = None
    if not args.sin_backup:
        copia = base.parent / "Backups" / f"bc-caja-pre-{version}-{sello}.sqlite3"
        copia.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(base))
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        destino = sqlite3.connect(str(copia))
        with destino:
            con.backup(destino)
        destino.close()
        con.close()
        registrar(f"Backup       {copia}")
        registrar(f"  sha256     {sha256(copia)}")
        registrar(f"  tamano     {copia.stat().st_size}")
        verif = sqlite3.connect(f"file:{copia.as_posix()}?mode=ro", uri=True)
        integro = verif.execute("PRAGMA integrity_check").fetchone()[0]
        verif.close()
        if not comprobar(integro == "ok", "el backup abre y esta integro"):
            registrar("STOP: sin un backup verificado no se aplica nada.")
            return 1
        registrar()

    registrar(f"Aplicando {archivo.name}")
    try:
        aplicar_una(base, version)
    except Exception as exc:  # noqa: BLE001
        registrar(f"FALLO: {exc}")
        if copia:
            registrar(f"Rollback: restaurar {copia} sobre {base}")
        return 1

    registrar()
    registrar("Post-checks")
    tablas = tablas_de(base)
    comprobar(version in aplicadas(base), f"schema_migrations registra la {version}")
    for t in esperado["tablas"]:
        comprobar(t in tablas, f"existe la tabla {t}")
    for t, cols in esperado["columnas"].items():
        presentes = columnas_de(base, t)
        for c in cols:
            comprobar(c in presentes, f"{t} tiene la columna {c}")
    for t in esperado["sin_tablas"]:
        comprobar(t not in tablas, f"{t} fue reemplazada y ya no existe")

    despues = radiografia(base)
    comprobar(despues["integridad"] == "ok", "integrity_check ok")
    comprobar(not despues["foreign_key_check"], "foreign_key_check sin violaciones")

    diffs = comparar(antes, despues)
    comprobar(not diffs, "ningun invariante productivo se movio")
    for d in diffs:
        registrar(f"       {d}")

    registrar()
    registrar(f"  sha256 base {despues['archivo']['sha256']}")
    registrar(f"  migraciones {len(despues['migraciones'])}")
    registrar()
    if fallas:
        registrar(f"RESULTADO: FALLA ({len(fallas)})")
        if copia:
            registrar(f"Rollback disponible: {copia}")
        return 1
    registrar(f"RESULTADO: PASS - migracion {version} aplicada y verificada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
